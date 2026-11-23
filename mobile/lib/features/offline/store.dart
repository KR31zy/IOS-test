import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

typedef JsonMap = Map<String, dynamic>;
JsonMap asMap(Object? value) => Map<String, dynamic>.from(value as Map);

/// Only routes with server-side, transactional idempotency may be queued.
bool queueable(String path) => RegExp(
  r'^/api/farms/[^/?]+/animals(?:/[^/?]+/events)?$',
).hasMatch(path);

bool cacheable(String path) => path == '/api/farms' || path == '/api/me' ||
    path == '/api/species/profiles' || RegExp(
      r'^/api/farms/[^/?]+/(?:summary|animals|events(?:\?category=[a-z]+)?|animals/[^/?]+/(?:events|cycle-summary))$',
    ).hasMatch(path);

const offlineWindow = Duration(hours: 24);
bool withinOfflineWindow(Object? value, DateTime now) {
  final at = DateTime.tryParse('$value');
  if (at == null) return false;
  final age = now.difference(at);
  return !age.isNegative && age < offlineWindow;
}

class PendingWrite {
  PendingWrite({required this.key, required this.path, required this.body,
    required this.createdAt, this.attempts = 0, this.issue, this.blocked = false});
  final String key, path, createdAt;
  final JsonMap body;
  final int attempts;
  final String? issue;
  final bool blocked;
  factory PendingWrite.fromJson(JsonMap j) => PendingWrite(key:j['key'] as String,
    path:j['path'] as String,body:asMap(j['body']),createdAt:j['createdAt'] as String,
    attempts:j['attempts'] as int,issue:j['issue'] as String?,blocked:j['blocked'] == true);
  JsonMap toJson() => {'key':key,'path':path,'body':body,'createdAt':createdAt,
    'attempts':attempts,'issue':issue,'blocked':blocked};
  PendingWrite state({required int attempts,String? issue,bool blocked=false}) =>
    PendingWrite(key:key,path:path,body:body,createdAt:createdAt,attempts:attempts,issue:issue,blocked:blocked);
}

/// One encrypted data file per API origin + account. All updates serialized,
/// with an atomic same-directory replacement. No plaintext farm data on disk.
class OfflineStore {
  OfflineStore._(this.file,this.key);
  final File file;
  final SecretKey key;
  final _cipher = AesGcm.with256bits();
  JsonMap _data = {'cache':<String,dynamic>{},'queue':<dynamic>[]};
  Future<void> _tail = Future<void>.value();
  static const maxBytes = 12 * 1024 * 1024;
  static const maxQueue = 300;

  static Future<OfflineStore> open(String base,String account, FlutterSecureStorage secure) async {
    final hash = await Sha256().hash(utf8.encode(jsonEncode([base,account])));
    final scope = hash.bytes.map((n)=>n.toRadixString(16).padLeft(2,'0')).join();
    final dir = await getApplicationSupportDirectory();
    final folder = Directory('${dir.path}/offline-v1');
    await folder.create(recursive:true);
    final file = File('${folder.path}/$scope.enc');
    final keyName = 'offline-key:$scope';
    var encoded = await secure.read(key:keyName);
    if (encoded == null) {
      if (await file.exists()) throw StateError('Offline encryption key unavailable. Contact support before resetting app data.');
      final key = await AesGcm.with256bits().newSecretKey();
      encoded = base64Encode(await key.extractBytes());
      await secure.write(key:keyName,value:encoded);
    }
    return openFile(file,SecretKey(base64Decode(encoded))); 
  }
  /// Allows the encrypted persistence layer to be tested without OS keychain plugins.
  static Future<OfflineStore> openFile(File file, SecretKey key) async {
    final store=OfflineStore._(file,key);
    await store._load();
    return store;
  }
  Future<void> _load() async {
    if (!await file.exists()) return;
    final bytes = await file.readAsBytes();
    if(bytes.length < 28 || bytes.length > maxBytes + 28) throw StateError('Offline file has an invalid size.');
    final box = SecretBox(bytes.sublist(12,bytes.length-16),nonce:bytes.sublist(0,12),mac:Mac(bytes.sublist(bytes.length-16)));
    final plaintext = await _cipher.decrypt(box,secretKey:key);
    _data = asMap(jsonDecode(utf8.decode(plaintext)));
  }
  Future<void> _change(void Function(JsonMap) change) {
    final task = _tail.then((_) async {
      final next = asMap(jsonDecode(jsonEncode(_data)));
      change(next);
      final data = utf8.encode(jsonEncode(next));
      if(data.length > maxBytes) throw StateError('Offline storage is full. Sync pending records first.');
      final box = await _cipher.encrypt(data,secretKey:key);
      final tmp = File('${file.path}.tmp');
      await tmp.writeAsBytes([...box.nonce,...box.cipherText,...box.mac.bytes],flush:true);
      await tmp.rename(file.path);
      _data = next;
    });
    _tail = task.then<void>((_) {},onError:(Object _,StackTrace __) {});
    return task;
  }
  List<PendingWrite> get queue => (_data['queue'] as List).map((j)=>PendingWrite.fromJson(asMap(j))).toList(growable:false);
  JsonMap? snapshot(String path) {
    final v = (_data['cache'] as Map)[path];
    return v == null ? null : asMap(jsonDecode(jsonEncode(v)));
  }
  Future<void> cache(String path,Object? value) => _change((d) {
    final cache = d['cache'] as Map;
    cache[path] = {'at':DateTime.now().toUtc().toIso8601String(),'value':value};
    // Limit snapshot count/size; never evict queued writes.
    while(cache.length > 80 || utf8.encode(jsonEncode(cache)).length > 8*1024*1024) {
      cache.remove(cache.keys.first);
    }
  });
  Future<void> clearCache() => _change((d)=>d['cache']=<String,dynamic>{});
  Future<void> removeSnapshot(String path) => _change((d)=>(d['cache'] as Map).remove(path));
  Future<void> retainFarms(Set<String> ids) => _change((d) {
    (d['cache'] as Map).removeWhere((k,v) {
      final match=RegExp(r'^/api/farms/([^/?]+)').firstMatch('$k');
      return match!=null && !ids.contains(match.group(1));
    });
  });
  Future<void> enqueue(PendingWrite write) => _change((d) {
    if(!queueable(write.path)) throw StateError('This operation requires a connection.');
    final q=d['queue'] as List;
    final existing=q.where((e)=>e['key']==write.key).firstOrNull;
    if(existing!=null) {
      if(existing['path']!=write.path || jsonEncode(existing['body'])!=jsonEncode(write.body)) {
        throw StateError('A pending submission cannot change its identity or payload.');
      }
      return;
    }
    if(q.length>=maxQueue) throw StateError('Pending queue is full. Synchronize before adding more.');
    q.add(write.toJson());
  });
  Future<void> update(PendingWrite write) => _change((d) {
    final q=d['queue'] as List;
    final i=q.indexWhere((e)=>e['key']==write.key);
    if(i>=0)q[i]=write.toJson();
  });
  Future<void> remove(String key) => _change((d)=>(d['queue'] as List).removeWhere((e)=>e['key']==key));
}
