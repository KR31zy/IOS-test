import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../features/offline/store.dart';

typedef RowData = Map<String, dynamic>;
RowData obj(dynamic v) => Map<String, dynamic>.from(v as Map);
List<RowData> rows(dynamic v) => (v as List).map(obj).toList();
String pretty(Object? v) => (v ?? '—').toString().replaceAll('_',' ');
DateTime? serverTime(Object? v) {
  final text='$v';
  // Legacy SQLite responses omit the offset from UTC timestamps.
  final hasTime=text.contains('T')||text.contains(' ');
  final hasZone=RegExp(r'(Z|[+-]\d{2}:?\d{2})$',caseSensitive:false).hasMatch(text);
  return DateTime.tryParse(hasTime&&!hasZone?'${text}Z':text);
}
String shortDate(Object? v) => serverTime(v)?.toLocal().toString().split('.').first ?? pretty(v);
String nonce() => List.generate(24, (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2,'0')).join();
class ApiError implements Exception {
  final int status; final String message;
  ApiError(this.status,this.message);
  @override String toString()=>message;
}
class ConnectionError extends ApiError {
  ConnectionError(String message):super(0,message);
}
class QueuedSubmission { const QueuedSubmission(); }
class Api extends ChangeNotifier {
  Api({http.Client? client}) : client=client??http.Client();
  final http.Client client;
  final storage=const FlutterSecureStorage(iOptions: IOSOptions(accessibility: KeychainAccessibility.unlocked_this_device));
  final syncSignal=ValueNotifier<int>(0);
  OfflineStore? _offlineStore;
  bool offline=false, syncing=false, _remember=false, usedOffline=false;
  int workspaceRevision=0;
  bool _disposed=false;
  Future<void> Function()? beforeClear;
  DateTime? _verified;
  String? syncIssue;
  DateTime? lastSyncAt;
  int _generation=0;
  List<PendingWrite> get pending=>_offlineStore?.queue??[];
  bool get offlineAccess {
    if(_verified==null||!withinOfflineWindow(_verified!.toIso8601String(),DateTime.now()))return false;
    // Do not extend the existing signed server session while offline.
    try{
      final payload=_cookie!.split('=')[1].split('.')[1];
      final claims=obj(jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(payload)))));
      return DateTime.now().millisecondsSinceEpoch < (claims['exp'] as num)*1000;
    }catch(_){return false;}
  }
  String get identityKey=>'offline-identity:$base';
  void signal(){if(!_disposed)syncSignal.value++;}
  void connection(bool value){if(value)usedOffline=true;if(offline!=value){offline=value;signal();}}
  bool get canSync=>signedIn&&!syncing;
  Future<void> openStore(String id) async {
    _offlineStore=await OfflineStore.open(base,id,storage);
    signal();
  }
  Future<void> verified(RowData account) async {
    _verified=DateTime.now().toUtc();
    if(_remember)await storage.write(key:identityKey,value:jsonEncode({'user':{'id':account['id'],'name':account['name'],'role':account['role']},'at':_verified!.toIso8601String()}));
  }
  Future<void> foregroundTick() async {
    if(!signedIn||_disposed)return;
    try{
      if(offline&&!offlineAccess){await clear();return;}
      if(offline||pending.any((p)=>!p.blocked))await synchronize();
    }catch(e){syncIssue='$e';signal();}
  }
  static const configured=String.fromEnvironment('API_BASE_URL');
  static const usernameMode=bool.fromEnvironment('USERNAME_AUTH',defaultValue:true);
  String? _selectedBase;
  String get serverPreference=>'server-url:v2:$configured';
  static String validateServer(String value,{bool allowHttp=!kReleaseMode}) {
    final u=Uri.tryParse(value.trim());
    if(u==null||u.host.isEmpty||u.userInfo.isNotEmpty||u.hasQuery||u.hasFragment||!['','/'].contains(u.path)||('https'!=u.scheme&&!(allowHttp&&u.scheme=='http'))) {
      throw ApiError(0,allowHttp?'Enter a valid HTTP or HTTPS server origin.':'Enter a valid HTTPS server origin.');
    }
    return u.origin;
  }
  bool get fixedServer => kReleaseMode && configured.isNotEmpty;
  Future<void> loadServer() async {
    if(configured.isNotEmpty)validateServer(configured);
    if(fixedServer)return;
    final saved=await storage.read(key:serverPreference);
    if(saved!=null){
      try{_selectedBase=validateServer(saved);}
      on ApiError{await storage.delete(key:serverPreference);}
    }
  }
  Future<void> setServer(String value) async {
    if(fixedServer||signedIn||syncing)throw ApiError(0,'Sign out before changing the server.');
    final next=validateServer(value);
    if(next==base)return;
    if(!needsServer)await clear(notify:false);
    await storage.write(key:serverPreference,value:next);
    _selectedBase=next;
  }
  bool get needsServer => _selectedBase==null&&configured.isEmpty;
  String get base => _selectedBase??(configured.isNotEmpty?validateServer(configured):'');
  /// Unauthenticated, read-only probe. Never carries cookies or follows redirects.
  Future<void> checkServer([String? candidate]) async {
    if(candidate==null&&needsServer)throw ApiError(0,'Set your farm server before signing in.');
    final origin=validateServer(candidate??base);
    try{
      final req=http.Request('GET',Uri.parse('$origin/api/health'))
        ..followRedirects=false..headers['Accept']='application/json';
      final response=await (() async => http.Response.fromStream(await client.send(req)))()
        .timeout(const Duration(seconds:8));
      if(response.statusCode!=200)throw ApiError(response.statusCode,'Health check returned HTTP ${response.statusCode}. Use the actual API server origin.');
      final body=jsonDecode(response.body);
      if(body is! Map||body['status']!='ok'||body['service']!='anirepro-api')throw ApiError(0,'This address is not a healthy AniRepro API.');
    } on TimeoutException{throw ConnectionError('Connection timed out. Check server availability and your network.');}
    on HandshakeException{throw ApiError(0,'TLS verification failed. Use a server with a valid HTTPS certificate.');}
    on SocketException{throw ConnectionError('Cannot reach $origin. For USB testing, restore ADB reverse; for Wi-Fi, use your Mac’s LAN address.');}
    on http.ClientException{throw ConnectionError('Cannot connect to $origin. Check the address, network, and server status.');}
    on FormatException{throw ApiError(0,'Server returned non-JSON data. Enter the API origin, not the website address.');}
  }
  String? _cookie, _csrf;
  RowData? user;
  bool get signedIn=>user!=null;
  String get storageKey=>'session:$base';
  Uri uri(String path) {
    if(needsServer)throw ApiError(0,'Set the farm server URL on the sign-in screen.');
    if(!path.startsWith('/api/'))throw ApiError(0,'Invalid API route.');
    final origin=validateServer(base);
    final u=Uri.parse('$origin$path');
    if (u.scheme!='https' && (kReleaseMode || u.scheme!='http')) throw ApiError(0,'Use an HTTPS API URL for release builds.');
    return u;
  }
  Map<String,String> headers(String method,{bool json=false,String? key})=>{
    'Accept':'application/json', if(json)'Content-Type':'application/json',
    if(_cookie!=null)'Cookie':_cookie!,
    if(_csrf!=null && method!='GET')'X-CSRF-Token':_csrf!,
    if(key!=null)'X-Idempotency-Key':key,
  };
  Future<http.Response> send(http.BaseRequest request,{bool auth=true}) async {
    final generation=_generation;
    final http.Response response;
    try {
      response = await (() async => http.Response.fromStream(await client.send(request)))()
          .timeout(const Duration(seconds:25));
    } on TimeoutException {
      throw ConnectionError(request.method == 'GET'
          ? 'The server took too long to respond. Check your connection and try again.'
          : 'The server took too long to respond. Check whether your change was saved before trying again.');
    } on HandshakeException {
      throw ApiError(0, 'The secure connection could not be verified. Contact your administrator.');
    } on SocketException {
      throw ConnectionError('Cannot reach the farm server. Check your network and server address.');
    } on http.ClientException {
      throw ConnectionError('Cannot connect to the farm server. Check your connection and try again.');
    }
    if(generation!=_generation)throw ApiError(0,'Session changed. Reopen the workspace.');
    if(response.statusCode<200||response.statusCode>=300){
      String message='Request failed (${response.statusCode})';
      try { final detail=obj(jsonDecode(response.body))['detail']; if(detail is String) message=detail; if(detail is List) message=detail.map((e)=>'${(e['loc'] as List).last}: ${e['msg']}').join('\n'); } catch (_) {}
      if(auth&&response.statusCode==401) {try{await _offlineStore?.clearCache();}finally{await clear();}}
      if(auth&&response.statusCode==403) await _offlineStore?.clearCache();
      throw ApiError(response.statusCode,message);
    }
    final cookie=response.headers['set-cookie'];
    final match=RegExp(r'anirepro_session=([^;, ]+)').firstMatch(cookie??'');
    if(match!=null) _cookie='anirepro_session=${match.group(1)}';
    return response;
  }
  Future<dynamic> request(String method,String path,{RowData? body,String? key,bool auth=true}) async {
    if(offline&&auth&&method!='GET')throw ApiError(0,'This action requires an online connection.');
    final req=http.Request(method,uri(path))..followRedirects=false..headers.addAll(headers(method,json:body!=null,key:key));
    if(body!=null)req.body=jsonEncode(body);
    final r=await send(req,auth:auth);
    if (r.bodyBytes.isEmpty) return null;
    try { return jsonDecode(utf8.decode(r.bodyBytes)); } on FormatException { throw ApiError(0, 'The server returned an unexpected response. Check the API address.'); }
  }
  Future<dynamic> get(String path) async {
    final store=_offlineStore;
    final generation=_generation;
    dynamic cached(){
      if(!offlineAccess)throw ApiError(0,'Offline access expired. Sign in online again.');
      final snap=store?.snapshot(path);
      if(!cacheable(path)||snap==null||!withinOfflineWindow(snap['at'],DateTime.now())) {
        throw ApiError(0,'This page has no recent offline copy. Open it while connected first.');
      }
      return snap['value'];
    }
    if(offline&&signedIn)return cached();
    try {
      final result=await request('GET',path);
      if(generation!=_generation)throw ApiError(0,'Session changed.');
      if(store!=null&&cacheable(path)) {
        if(path=='/api/farms'){
          final old=store.snapshot(path)?['value'];
          // A changed permission or membership invalidates all cached farm views.
          if(old==null){await store.clearCache();}
          else if(jsonEncode(old)!=jsonEncode(result)){
            await store.clearCache();
            if(generation==_generation){workspaceRevision++;notifyListeners();}
          }
          await store.retainFarms(rows(result).map((r)=>'${r['id']}').toSet());
        }
        if(generation!=_generation)throw ApiError(0,'Session changed.');
        try{await store.cache(path,result);}catch(e){syncIssue='Could not save offline snapshot: $e';signal();}
      }
      return result;
    } on ConnectionError {
      if(generation!=_generation||!signedIn)rethrow;
      connection(true);
      return cached();
    }
  }
  Future<dynamic> post(String path,RowData body,{String? key}) async {
    if(!queueable(path)) {
      if(offline)throw ApiError(0,'This action requires an online connection.');
      return request('POST',path,body:body,key:key);
    }
    final store=_offlineStore;
    if(store==null||!signedIn)throw ApiError(0,'Sign in before submitting a record.');
    if(!offlineAccess&&offline)throw ApiError(0,'Offline access expired. Sign in online.');
    final id=key??nonce();
    final existing=store.queue.where((p)=>p.key==id).firstOrNull;
    if(existing?.blocked==true)throw ApiError(409,'This submission needs review in Sync center.');
    final entry=PendingWrite(key:id,path:path,body:obj(jsonDecode(jsonEncode(body))),createdAt:DateTime.now().toUtc().toIso8601String());
    final generation=_generation;
    await store.enqueue(entry);
    signal();
    if(offline||syncing||generation!=_generation)return const QueuedSubmission();
    syncing=true;signal();
    try{return await deliver(store,existing??entry);}
    finally{syncing=false;signal();}
  }
  Future<dynamic> deliver(OfflineStore store,PendingWrite entry) async {
    final generation=_generation;
    final attempted=entry.state(attempts:entry.attempts+1);
    await store.update(attempted);
    if(generation!=_generation||!signedIn)return const QueuedSubmission();
    dynamic result;
    try {
      result=await request('POST',entry.path,body:entry.body,key:entry.key);
    } on ConnectionError catch(e){
      await store.update(attempted.state(attempts:attempted.attempts,issue:e.message));
      if(generation==_generation&&signedIn)connection(true);
      return const QueuedSubmission();
    } on ApiError catch(e){
      final retryable=e.status==401||e.status==408||e.status==429||e.status>=500;
      await store.update(attempted.state(attempts:attempted.attempts,issue:e.message,blocked:!retryable));
      if(retryable)return const QueuedSubmission();
      throw ApiError(e.status,'${e.message} — submission retained in Sync center for review.');
    }
    // If persistence fails, retain the same idempotency key for later replay.
    await store.remove(entry.key);
    return result;
  }
  Future<void> synchronize() async {
    if(!canSync)return;
    final store=_offlineStore;
    if(store==null)return;
    final generation=_generation;
    final account='${user!['id']}';
    syncing=true;syncIssue=null;signal();
    try{
      // Always verify the real session before replay; never trust cached roles.
      final session=obj(await request('GET','/api/auth/session'));
      if('${obj(session['user'])['id']}'!=account) {await clear();return;}
      if(generation!=_generation)return;
      _csrf=session['csrf_token'] as String;
      await verified(obj(session['user']));
      connection(false);
      await get('/api/farms');
      if(offline||generation!=_generation)return;
      for(final entry in store.queue){
        if(entry.blocked)continue;
        if(generation!=_generation||offline)break;
        try{
          final result=await deliver(store,entry);
          if(result is QueuedSubmission)break;
        } on ApiError catch(e){syncIssue=e.message;}
      }
      if(generation==_generation&&!offline&&store.queue.isEmpty)lastSyncAt=DateTime.now();
    } on ConnectionError catch(e){if(generation==_generation)connection(true);syncIssue=e.message;}
      catch(e){syncIssue='$e';}
    finally{syncing=false;signal();}
  }
  Future<void> retryPending(String key) async {
    if(syncing)return;
    final store=_offlineStore;
    final entry=store?.queue.where((p)=>p.key==key).firstOrNull;
    if(store==null||entry==null)return;
    await store.update(entry.state(attempts:entry.attempts));
    await synchronize();
  }
  Future<void> discardPending(String key) async {
    if(syncing)return;
    await _offlineStore?.remove(key);signal();
  }
  Future<void> authenticate(String path,RowData body,bool remember) async {
    await checkServer();
    await clear(notify:false);
    final result=obj(await request('POST',path,body:body,auth:false));
    _csrf=result['csrf_token'] as String?;
    if(_cookie==null||_csrf==null)throw ApiError(0,'Server did not return a valid session.');
    final account=obj(result['user']);
    await openStore('${account['id']}');
    await _offlineStore!.clearCache();
    _remember=remember;
    await verified(account);
    if(remember)await storage.write(key:storageKey,value:_cookie);
    user=account;notifyListeners();
  }
  Future<void> restore() async {
    await loadServer();
    if(needsServer)return;
    _cookie=await storage.read(key:storageKey);
    if(_cookie==null)return;
    _remember=true;
    try {
      final result=obj(await request('GET','/api/auth/session'));
      _csrf=result['csrf_token'] as String;
      final account=obj(result['user']);
      await openStore('${account['id']}');
      await verified(account);
      user=account;notifyListeners();
    } on ConnectionError {
      final raw=await storage.read(key:identityKey);
      if(raw==null)rethrow;
      final saved=obj(jsonDecode(raw));
      _verified=DateTime.tryParse('${saved['at']}');
      if(!offlineAccess)throw ApiError(0,'Offline session expired. Connect to sign in.');
      final account=obj(saved['user']);
      await openStore('${account['id']}');
      if(_offlineStore?.snapshot('/api/farms')==null)throw ApiError(0,'No offline farm workspace. Connect to sign in.');
      _verified=DateTime.parse(saved['at'] as String);
      connection(true);user=account;notifyListeners();
    } on ApiError catch(e){if(e.status!=401)rethrow;}
  }
  Future<void> clear({bool notify=true}) async {
    _generation++;
    _cookie=null;_csrf=null;user=null;_verified=null;_remember=false;offline=false;
    _offlineStore=null;usedOffline=false;syncIssue=null;lastSyncAt=null;
    try{await beforeClear?.call();}catch(_){/* OS alerts are best effort; generic content only. */}
    try{if(!needsServer){await storage.delete(key:storageKey);await storage.delete(key:identityKey);}}
    finally{signal();if(notify)notifyListeners();}
  }
  Future<void> logout() async {
    if(syncing)throw ApiError(0,'Wait for synchronization to finish before signing out.');
    final store=_offlineStore;
    try{try{await beforeClear?.call();}catch(_){/* generic push leases still expire */}
      if(!offline)await request('POST','/api/auth/logout',body:{});}
    finally{try{await store?.clearCache();}finally{await clear();}}
  }
  Future<http.Response> download(String path) async {
    if(offline)throw ApiError(0,'Downloads require an online connection.');
    return send(http.Request('GET',uri(path))..followRedirects=false..headers.addAll(headers('GET')));
  }
  Future<void> upload(String path,String file,String name,String mime,{String? eventId}) async {
    if(offline)throw ApiError(0,'Attachments require an online connection.');
    final req=http.MultipartRequest('POST',uri(path))..followRedirects=false..headers.addAll(headers('POST',key:nonce()));
    if(eventId!=null)req.fields['event_id']=eventId;
    // The caller validates type and size before opening the request.
    final part=await http.MultipartFile.fromPath('file',file,filename:name,contentType:MediaType.parse(mime));
    req.files.add(part);await send(req);
  }
  @override void dispose(){_disposed=true;client.close();syncSignal.dispose();super.dispose();}
}
