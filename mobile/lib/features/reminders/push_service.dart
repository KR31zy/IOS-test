import 'dart:async';
import 'dart:io';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../widgets/common.dart';
import 'native_alerts.dart';

/// Optional, provisioned FCM. No tokens sent to the core API unless user opts in.
class PushService {
  PushService._();
  static final instance=PushService._();
  static const configured=bool.fromEnvironment('ENABLE_REMOTE_PUSH');
  StreamSubscription<String>? _refresh;
  StreamSubscription<RemoteMessage>? _messages;
  String? _token,_owner;
  int _generation=0;
  String tokenKey(Api api,String owner)=>'push-token:${api.base}:$owner';
  bool get enabled=>_token!=null;
  Future<void> _init() async {
    if(!configured||(!Platform.isAndroid&&!Platform.isIOS))throw StateError('Remote push is not provisioned for this build.');
    if(Firebase.apps.isEmpty)await Firebase.initializeApp();
  }
  Future<void> enable(Api api) async {
    if(api.offline||!api.signedIn)throw StateError('Sign in online to enable remote push.');
    final owner='${api.user!['id']}';
    final generation=++_generation;
    await _init();
    if(!await NativeAlerts.instance.permission())throw StateError('Notification permission denied.');
    final messaging=FirebaseMessaging.instance;
    await messaging.requestPermission(alert:true,badge:false,sound:true);
    await messaging.setForegroundNotificationPresentationOptions(alert:false,badge:false,sound:false);
    if(Platform.isIOS&&await messaging.getAPNSToken()==null)throw StateError('APNs token not ready. Verify Apple push configuration, then retry.');
    final token=await messaging.getToken();
    if(token==null||generation!=_generation||!api.signedIn||'${api.user!['id']}'!=owner)throw StateError('Push token unavailable or session changed.');
    await api.request('POST','/api/mobile/push/register',body:{'token':token});
    if(generation!=_generation||!api.signedIn||'${api.user!['id']}'!=owner){await messaging.deleteToken();throw StateError('Session changed. Enable push again.');}
    _token=token;_owner=owner;
    await api.storage.write(key:tokenKey(api,owner),value:token);
    await _refresh?.cancel();await _messages?.cancel();
    _refresh=messaging.onTokenRefresh.listen((newToken) async {
      if(generation!=_generation||!api.signedIn||'${api.user!['id']}'!=_owner||api.offline)return;
      try{await api.request('POST','/api/mobile/push/register',body:{'token':newToken,'previous_token':_token});if(generation==_generation){_token=newToken;await api.storage.write(key:tokenKey(api,owner),value:newToken);}}catch(_){/* user can re-enable; old lease expires */}
    });
    _messages=FirebaseMessaging.onMessage.listen((message) async {
      if(generation==_generation&&api.signedIn&&'${api.user!['id']}'==_owner){try{await NativeAlerts.instance.inboxAlert();}catch(_){}}
    });
  }
  Future<void> disable(Api api) async {
    _generation++;
    final owner=_owner??api.user?['id']?.toString();
    String? token=_token;
    _token=null;_owner=null;
    await _refresh?.cancel();_refresh=null;await _messages?.cancel();_messages=null;
    if(!configured)return;
    if(owner!=null){try{token??=await api.storage.read(key:tokenKey(api,owner));await api.storage.delete(key:tokenKey(api,owner));}catch(_){}}
    // On a cold restart there may still be a previously leased native token.
    if(Firebase.apps.isEmpty){try{await _init();}catch(_){return;}}
    try{if(token!=null&&api.signedIn&&!api.offline)await api.request('POST','/api/mobile/push/unregister',body:{'token':token});}catch(_){/* short-lived server lease; generic messages only */}
    try{await FirebaseMessaging.instance.deleteToken();}catch(_){/* expired server lease is fallback */}
  }
}
class PushSettingsPage extends StatefulWidget {
  const PushSettingsPage({super.key,required this.api});final Api api;
  @override State<PushSettingsPage> createState()=>_PushSettingsPageState();
}
class _PushSettingsPageState extends State<PushSettingsPage>{
  bool busy=false; String? message;
  Future<void> act(bool enable)async{
    setState(()=>busy=true);
    try{
      if(enable){await PushService.instance.enable(widget.api);message='Registered for this server session. Re-enable after signing in again.';}
      else{await PushService.instance.disable(widget.api);message='Local push token removed where available; any remaining server lease expires with the session.';}
    }catch(e){message='$e';}finally{if(mounted)setState(()=>busy=false);}
  }
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Remote push')),body:ListView(padding:const EdgeInsets.all(20),children:[
    const Icon(Icons.notifications_active_outlined,size:56),const SizedBox(height:16),
    Text(PushService.configured?'Remote farm updates':'Remote push not configured',style:Theme.of(context).textTheme.headlineSmall),
    const Text('Receive generic alerts for new authorized inbox events. Open the app and sign in to see details. Remote alerts require a provisioned Firebase project, an active server lease and internet access.'),const SizedBox(height:16),
    BrandButton('Enable remote push',busy:busy,action:PushService.configured&&!widget.api.offline?()=>act(true):null),
    TextButton(onPressed:busy||!PushService.configured?null:()=>act(false),child:const Text('Disable remote push')),
    if(message!=null)Text(message!),
    const Text('Delivery is best effort. Device reminder alarms work separately without Firebase.'),
  ]));
}
