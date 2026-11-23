import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/material.dart';
import '../core/api.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
class Splash extends StatefulWidget {
  const Splash({super.key});
  @override State<Splash> createState()=>_SplashState();
}

class _SplashState extends State<Splash> with SingleTickerProviderStateMixin {
  late final AnimationController controller;
  @override void initState() {
    super.initState();
    controller=AnimationController(vsync:this,duration:const Duration(milliseconds:1500))..forward();
  }
  @override void dispose() {controller.dispose();super.dispose();}
  @override Widget build(BuildContext context)=>Scaffold(body:Container(
    decoration:const BoxDecoration(gradient:brandGradient),
    child:Center(child:Column(mainAxisSize:MainAxisSize.min,children:[
      AnimatedBuilder(animation:controller,builder:(context,child){
        final progress=MediaQuery.disableAnimationsOf(context)?1.0:Curves.easeOutCubic.transform(controller.value);
        return Opacity(opacity:progress,child:Transform.scale(scale:.86+.14*progress,child:child));
      },child:Container(width:164,height:164,padding:const EdgeInsets.all(17),
        decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(42),
          boxShadow:const [BoxShadow(color:Colors.black26,blurRadius:28,offset:Offset(0,12))]),
        child:Image.asset('assets/logo.png',semanticLabel:'AniRepro 360 logo'))),
      const SizedBox(height:28),
      const Text('AniRepro 360',style:TextStyle(color:Colors.white,fontSize:30,fontWeight:FontWeight.w800)),
      const SizedBox(height:6),
      const Text('Health • Fertility • Farm intelligence',style:TextStyle(color:Colors.white70)),
      const SizedBox(height:34),
      const SizedBox(width:96,child:LinearProgressIndicator(color:Colors.white,backgroundColor:Colors.white24)),
    ])),
  ));
}
class AuthScreen extends StatefulWidget {const AuthScreen({super.key,required this.api});final Api api;@override State<AuthScreen> createState()=>_AuthScreenState();}
class _AuthScreenState extends State<AuthScreen>{final form=GlobalKey<FormState>();final identity=TextEditingController(), email=TextEditingController(), password=TextEditingController(), name=TextEditingController(), farm=TextEditingController(), token=TextEditingController();String mode='login';bool busy=false,hidden=true,remember=true;String? error,notice;int get min=>Api.usernameMode?8:12;@override void dispose(){for(final c in [identity,email,password,name,farm,token]){c.dispose();}super.dispose();}void switchMode(String m)=>setState((){mode=m;error=null;notice=null;password.clear();});Future<void> submit()async{if(!form.currentState!.validate())return;FocusScope.of(context).unfocus();setState((){busy=true;error=null;notice=null;});try{final api=widget.api;if(mode=='recovery'||mode=='reset')await api.checkServer();switch(mode){case 'register':await api.authenticate('/api/auth/register',{'email':email.text.trim(),'password':password.text,'full_name':name.text.trim(),'farm_name':farm.text.trim(),if(Api.usernameMode)'username':identity.text.trim()},remember);break;case 'recovery':final r=obj(await api.request('POST','/api/auth/recovery/request',body:{'email':email.text.trim()},auth:false));if(mounted)setState(()=>notice='${r['message']}');break;case 'reset':await api.request('POST','/api/auth/recovery/complete',body:{'token':(Uri.tryParse(token.text.trim())?.queryParameters['token']??token.text.trim()),'password':password.text},auth:false);if(mounted){switchMode('login');setState(()=>notice='Password updated. Sign in again.');}break;case 'join':await api.authenticate('/api/auth/invitations/accept',{'token':(Uri.tryParse(token.text.trim())?.queryParameters['token']??token.text.trim()),'password':password.text,'full_name':name.text.trim()},remember);break;default:final id=identity.text.trim();await api.authenticate('/api/auth/login',{if(Api.usernameMode&&!id.contains('@'))'username':id else 'email':id,'password':password.text},remember);}}catch(e){if(mounted)setState(()=>error='$e');}finally{if(mounted)setState(()=>busy=false);}}

int socialAttempt=0;
Future<void> social(String provider) async {
  final attempt=++socialAttempt;
  FocusScope.of(context).unfocus();
  setState((){busy=true;error=null;notice='Opening ${provider=='google'?'Google':'Apple'} sign-in…';});
  try {
    final api=widget.api;
    if(api.needsServer)throw ApiError(0,'Set your farm server first. Google and Apple require HTTPS.');
    if(Uri.parse(api.base).scheme!='https')throw ApiError(0,'Google and Apple sign-in require a trusted HTTPS farm server.');
    await api.checkServer();
    final start=obj(await api.request('POST','/api/auth/social/start',body:{'provider':provider},auth:false));
    if(!mounted||attempt!=socialAttempt)return;
    final url=Uri.parse('${start['authorization_url']}');
    final expected=provider=='google'?'accounts.google.com':'appleid.apple.com';
    if(url.scheme!='https'||url.host!=expected||url.userInfo.isNotEmpty||url.port!=443)throw ApiError(0,'Unexpected sign-in provider address.');
    final proof={'flow':start['flow'],'proof':start['proof']};
    if(!await launchUrl(url,mode:LaunchMode.externalApplication))throw ApiError(0,'Could not open your browser.');
    if(!mounted||attempt!=socialAttempt)return;
    setState(()=>notice='Complete sign-in in your browser, then return here.');
    final deadline=DateTime.now().add(const Duration(minutes:9));
    RowData? ready;
    while(mounted&&attempt==socialAttempt&&DateTime.now().isBefore(deadline)){
      await Future<void>.delayed(const Duration(seconds:3));
      if(!mounted||attempt!=socialAttempt)return;
      try {
        final result=obj(await api.request('POST','/api/auth/social/status',body:proof,auth:false));
        if(result['status']=='ready'){ready=result;break;}
        if(!['pending','verifying'].contains(result['status']))throw ApiError(0,'Sign-in was cancelled or could not be verified.');
      } on ConnectionError {continue;}
    }
    if(!mounted||attempt!=socialAttempt)return;
    if(ready==null)throw ApiError(0,'Sign-in expired. Please try again.');
    final action=ready['action'];
    RowData details={};
    if(action=='register'||action=='link'){
      final result=await socialDetails(ready);
      if(result==null||!mounted||attempt!=socialAttempt)return;
      details=result;
    }else if(action!='login'){throw ApiError(0,'A verified email is needed for first-time sign-up.');}
    if(!mounted||attempt!=socialAttempt)return;
    setState(()=>notice=null);
    await api.authenticate('/api/auth/social/finish',{...proof,...details},remember);
  }catch(e){if(mounted&&attempt==socialAttempt)setState(()=>error='$e');}
  finally{if(mounted&&attempt==socialAttempt)setState((){busy=false;notice=null;});}
}
Future<RowData?> socialDetails(RowData value) async {
  final linking=value['action']=='link';
  String fullName='${value['name']??''}',farmName='',existingPassword='';
  final key=GlobalKey<FormState>();
  return showDialog<RowData>(context:context,builder:(ctx)=>AlertDialog(
    title:Text(linking?'Link your AniRepro account':'Create your farm workspace'),
    content:Form(key:key,child:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,crossAxisAlignment:CrossAxisAlignment.start,children:[
      Text('${value['email']??''}'),const SizedBox(height:12),
      Text(linking?'An account already exists. Confirm its password to link this sign-in method.':'Your provider verified your email. Enter your details to create a new, private farm.'),const SizedBox(height:12),
      if(linking)TextFormField(obscureText:true,decoration:const InputDecoration(labelText:'Existing AniRepro password'),onChanged:(v)=>existingPassword=v,validator:(v)=>(v??'').isEmpty?'Enter your password':null)
      else ...[TextFormField(initialValue:fullName,decoration:const InputDecoration(labelText:'Full name'),onChanged:(v)=>fullName=v,validator:(v)=>(v??'').trim().length<2?'Enter your name':null),const SizedBox(height:12),TextFormField(decoration:const InputDecoration(labelText:'Farm name'),onChanged:(v)=>farmName=v,validator:(v)=>(v??'').trim().length<2?'Enter your farm name':null)]
    ]))),actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Cancel')),FilledButton(onPressed:(){if(key.currentState!.validate())Navigator.pop(ctx,linking?{'password':existingPassword}:{'full_name':fullName.trim(),'farm_name':farmName.trim()});},child:Text(linking?'Link and sign in':'Create account'))]));
}
Widget socialButtons()=>Column(children:[
  Row(children:[const Expanded(child:Divider()),Padding(padding:const EdgeInsets.all(10),child:Text('Or continue with',style:Theme.of(context).textTheme.bodySmall)),const Expanded(child:Divider())]),
  LayoutBuilder(builder:(ctx,c){final buttons=[
    OutlinedButton.icon(onPressed:busy?null:()=>social('google'),icon:Image.asset('assets/google_g.png',width:20,height:20),label:const Text('Google'),style:OutlinedButton.styleFrom(backgroundColor:const Color(0xffedf3f4),foregroundColor:navy,minimumSize:const Size(0,52),side:BorderSide.none)),
    OutlinedButton.icon(onPressed:busy?null:()=>social('apple'),icon:const Icon(Icons.apple,color:Colors.black,size:24),label:const Text('Apple'),style:OutlinedButton.styleFrom(backgroundColor:const Color(0xffedf3f4),foregroundColor:navy,minimumSize:const Size(0,52),side:BorderSide.none))];
    return c.maxWidth<260?Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[buttons[0],const SizedBox(height:10),buttons[1]]):Row(children:[Expanded(child:buttons[0]),const SizedBox(width:12),Expanded(child:buttons[1])]);}),
  if(busy&&notice!=null)TextButton(onPressed:(){socialAttempt++;setState((){busy=false;notice=null;});},child:const Text('Cancel browser sign-in')),
]);

Future<void> testConnection() async {
  setState((){busy=true;error=null;notice=null;});
  try{await widget.api.checkServer();if(mounted)setState(()=>notice='Connected to AniRepro farm server.');}
  catch(e){if(mounted)setState(()=>error='$e');}
  finally{if(mounted)setState(()=>busy=false);}
}
Future<void> changeServer() async {
  String value=widget.api.needsServer?'':widget.api.base;
  String? issue;
  bool checking=false;
  final next=await showDialog<String>(context:context,builder:(ctx)=>StatefulBuilder(builder:(ctx,update)=>AlertDialog(
    title:const Text('Connect to your farm server'),
    content:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,crossAxisAlignment:CrossAxisAlignment.stretch,children:[
      const Text('Enter the trusted farm API origin. Test the connection before saving.'),
      if(!kReleaseMode)const Padding(padding:EdgeInsets.symmetric(vertical:8),child:Text('USB: http://127.0.0.1:8000 (ADB reverse required). Wi-Fi: use the server computer’s LAN address. Emulator: http://10.0.2.2:8000. Use test data only.')),
      TextFormField(initialValue:value,enabled:!checking,keyboardType:TextInputType.url,autocorrect:false,decoration:const InputDecoration(labelText:'Server URL',hintText:'https://api.example.org'),onChanged:(v)=>value=v),
      if(checking)const LinearProgressIndicator(),
      if(issue!=null)Padding(padding:const EdgeInsets.only(top:10),child:Text(issue!,style:TextStyle(color:Theme.of(ctx).colorScheme.error))),
    ])),actions:[TextButton(onPressed:checking?null:()=>Navigator.pop(ctx),child:const Text('Cancel')),
      FilledButton(onPressed:checking?null:()async{
        update((){checking=true;issue=null;});
        try{await widget.api.checkServer(value);if(ctx.mounted)Navigator.pop(ctx,value);}
        catch(e){if(ctx.mounted)update((){checking=false;issue='$e';});}
      },child:const Text('Test and save'))])));
  if(next==null||!mounted)return;
  try{await widget.api.setServer(next);if(mounted)setState((){error=null;notice='Server verified and saved.';password.clear();});}catch(e){if(mounted)setState(()=>error='$e');}
}
Widget field(TextEditingController c,String label,IconData icon,{bool optional=false,bool emailField=false,bool secret=false,int minimum=1})=>Padding(padding:const EdgeInsets.only(bottom:14),child:TextFormField(controller:c,enabled:!busy,obscureText:secret&&hidden,autocorrect:!secret,keyboardType:emailField?TextInputType.emailAddress:TextInputType.text,autofillHints:secret?[mode=='login'?AutofillHints.password:AutofillHints.newPassword]:emailField?[AutofillHints.email]:null,decoration:InputDecoration(labelText:label,prefixIcon:Icon(icon),suffixIcon:secret?IconButton(tooltip:hidden?'Show password':'Hide password',onPressed:()=>setState(()=>hidden=!hidden),icon:Icon(hidden?Icons.visibility_off_outlined:Icons.visibility_outlined)):null),validator:(v){final t=secret?(v??''):(v??'').trim();if(optional&&t.isEmpty)return null;if(t.length<minimum)return '$label requires at least $minimum characters';if(emailField&&!t.contains('@'))return 'Enter a valid email';if(label=='Username'&&!RegExp(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}$').hasMatch(t))return 'Use 3–32 letters, numbers, dots, underscores or hyphens';return null;}));
@override Widget build(BuildContext context){final login=mode=='login',reg=mode=='register',recovery=mode=='recovery',reset=mode=='reset',join=mode=='join';return Scaffold(body:SafeArea(top:false,child:SingleChildScrollView(child:Column(children:[Container(width:double.infinity,decoration:const BoxDecoration(gradient:brandGradient,borderRadius:BorderRadius.vertical(bottom:Radius.circular(38))),child:SafeArea(bottom:false,child:Padding(padding:const EdgeInsets.fromLTRB(24,24,18,32),child:Row(children:[const Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('AniRepro\n360',style:TextStyle(fontSize:33,height:1.05,fontWeight:FontWeight.w900,color:Colors.white)),SizedBox(height:12),Text('Better animal health.\nSmarter farm decisions.',style:TextStyle(color:Colors.white70,fontSize:15,height:1.4))])),Flexible(child:Container(padding:const EdgeInsets.all(10),decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(32)),child:Image.asset('assets/logo.png',height:145,fit:BoxFit.contain)))])))),Center(child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:520),child:Padding(padding:const EdgeInsets.fromLTRB(24,29,24,24),child:AutofillGroup(child:Form(key:form,child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Text(login?'Welcome Back':reg?'Create your account':recovery?'Forgot password?':reset?'Set new password':'Join a farm',style:TextStyle(fontSize:30,fontWeight:FontWeight.w800,color:readableText(context))),const SizedBox(height:8),Text(login?'Your farm workspace is ready.':reg?'Start with your own farm.':join?'Use the token from your invitation.':'Recover access securely.',style:Theme.of(context).textTheme.bodyMedium),Padding(padding:const EdgeInsets.only(top:10),child:Text(widget.api.needsServer?'Farm server not configured':widget.api.base,style:Theme.of(context).textTheme.bodySmall)),Wrap(spacing:8,children:[if(!widget.api.fixedServer)TextButton.icon(onPressed:busy?null:changeServer,icon:const Icon(Icons.dns_outlined),label:Text(widget.api.needsServer?'Set farm server':'Change farm server')),if(!widget.api.needsServer)TextButton.icon(onPressed:busy?null:testConnection,icon:const Icon(Icons.wifi_find),label:const Text('Test connection'))]),const SizedBox(height:24),if(reg||join)field(name,'Full name',Icons.person_outline,optional:join,minimum:2),if(reg)field(farm,'Farm name',Icons.agriculture,minimum:2),if(login||(reg&&Api.usernameMode))field(identity,Api.usernameMode?(login?'Username or email':'Username'):'Email address',Icons.person_outline,emailField:!Api.usernameMode),if(reg||recovery)field(email,'Email address',Icons.mail_outline,emailField:true),if(reset||join)field(token,'${join?'Invitation':'Recovery'} token',Icons.key,minimum:32),if(!recovery)field(password,'Password',Icons.lock_outline,secret:true,minimum:reg||reset?min:1),if(reg||reset)Text('Minimum $min characters. Use a strong, unique password.',style:Theme.of(context).textTheme.bodySmall),if(login)Wrap(alignment:WrapAlignment.spaceBetween,crossAxisAlignment:WrapCrossAlignment.center,children:[Row(mainAxisSize:MainAxisSize.min,children:[Checkbox(value:remember,onChanged:busy?null:(v)=>setState(()=>remember=v??false),activeColor:green),const Text('Keep me signed in')]),TextButton(onPressed:busy?null:()=>switchMode('recovery'),child:const Text('Forgot password?',style:TextStyle(color:green)))]),if(error!=null)Padding(padding:const EdgeInsets.symmetric(vertical:10),child:Text(error!,style:TextStyle(color:Theme.of(context).colorScheme.error))),if(notice!=null)Padding(padding:const EdgeInsets.symmetric(vertical:10),child:Text(notice!,style:const TextStyle(color:green))),const SizedBox(height:14),BrandButton(login?'Sign in':reg?'Create account':recovery?'Send recovery link':reset?'Reset password':'Accept invitation',busy:busy,action:submit),const SizedBox(height:12),if(login||reg)socialButtons(),if(login)...[Row(children:[const Expanded(child:Divider()),Padding(padding:const EdgeInsets.all(10),child:Text('New to AniRepro?',style:Theme.of(context).textTheme.bodySmall)),const Expanded(child:Divider())]),OutlinedButton(onPressed:busy?null:()=>switchMode('register'),child:const Text('Create an account')),TextButton(onPressed:busy?null:()=>switchMode('join'),child:const Text('I have a farm invitation'))]else TextButton(onPressed:busy?null:()=>switchMode('login'),child:const Text('Back to sign in')),if(recovery)TextButton(onPressed:busy?null:()=>switchMode('reset'),child:const Text('I have a recovery token'))])),)))),]))));}
}
