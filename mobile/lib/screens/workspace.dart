import 'package:flutter/material.dart';
import '../core/api.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../features/clinical/module_ui.dart';
import 'records.dart';
import 'extras.dart';
import '../features/reminders/reminder_page.dart';
import '../features/offline/sync_page.dart';
class Workspace extends StatefulWidget{const Workspace({super.key,required this.api});final Api api;@override State<Workspace> createState()=>_WorkspaceState();}
class _WorkspaceState extends State<Workspace>{late Future<dynamic> farms;String? current;String selectedTab='Home';@override void initState(){super.initState();farms=widget.api.get('/api/farms');}void refresh(){if(mounted)setState(()=>farms=widget.api.get('/api/farms'));}@override Widget build(BuildContext context)=>FutureBuilder<dynamic>(future:farms,builder:(c,s){if(s.connectionState!=ConnectionState.done)return const Scaffold(body:Loading());if(s.hasError)return Scaffold(body:MessagePane('${s.error}',retry:refresh));final data=rows(s.data);if(data.isEmpty)return Scaffold(appBar:AppBar(title:const Text('AniRepro 360'),actions:[IconButton(onPressed:()=>openPage(c,SettingsPage(api:widget.api)),icon:const Icon(Icons.person))]),body:MessagePane('No active farm membership. Contact your farm manager.',retry:refresh));final f=data.firstWhere((r)=>r['id']==current,orElse:()=>data.first);final tabs=<(String,IconData,Widget)>[('Home',Icons.home_outlined,Dashboard(api:widget.api,farm:f,farms:data,select:(id)=>setState((){current=id;selectedTab='Home';}))),if(allowed(f,'animals.view'))('Animals',Icons.pets,AnimalsPage(api:widget.api,farm:f)),if(allowed(f,'health.view'))('Health',Icons.monitor_heart_outlined,CategoryPage(api:widget.api,farm:f,category:'health')),if(allowed(f,'reports.view'))('Reports',Icons.bar_chart,ReportsPage(api:widget.api,farm:f)),('More',Icons.grid_view,MorePage(api:widget.api,farm:f,onReturnHome:(){if(mounted)setState(()=>selectedTab='Home');}))];final match=tabs.indexWhere((t)=>t.$1==selectedTab);final i=match<0?0:match;return PopScope(canPop:selectedTab=='Home',onPopInvokedWithResult:(didPop,result){if(!didPop&&mounted&&selectedTab!='Home')setState(()=>selectedTab='Home');},child:Scaffold(body:AnimatedSwitcher(duration:MediaQuery.disableAnimationsOf(c)?Duration.zero:const Duration(milliseconds:220),child:KeyedSubtree(key:ValueKey('${f['id']}-${tabs[i].$1}'),child:tabs[i].$3)),bottomNavigationBar:NavigationBar(selectedIndex:i,onDestinationSelected:(v)=>setState(()=>selectedTab=tabs[v].$1),destinations:tabs.map((t)=>NavigationDestination(icon:Icon(t.$2),label:t.$1)).toList())));});}
class Dashboard extends StatelessWidget{const Dashboard({super.key,required this.api,required this.farm,required this.farms,required this.select});final Api api;final RowData farm;final List<RowData> farms;final ValueChanged<String> select;@override Widget build(BuildContext context)=>DataPage(title:'AniRepro 360',actions:[IconButton(tooltip:'Sync center',onPressed:()=>openPage(context,SyncPage(api:api,farm:farm)),icon:const Icon(Icons.cloud_sync_outlined)),IconButton(tooltip:'Notifications',onPressed:()=>openPage(context,NotificationsPage(api:api)),icon:const Icon(Icons.notifications_none)),IconButton(tooltip:'Profile',onPressed:()=>openPage(context,SettingsPage(api:api)),icon:const Icon(Icons.account_circle_outlined))],load:()async=>Future.wait([if(allowed(farm,'dashboard.view'))api.get('${farmPath(farm)}/summary')else Future.value(<String,dynamic>{}),if(allowed(farm,'animals.view'))api.get('${farmPath(farm)}/events')else Future.value([])]),content:(c,data,reload){final totals=obj(data[0]);final events=rows(data[1]);final metrics=< (String,String,IconData)>[('animals','Animals',Icons.pets),if(allowed(farm,'health.view'))('health_records','Health records',Icons.monitor_heart),if(allowed(farm,'reproduction.view'))('pregnancies_confirmed','Animals ever confirmed pregnant',Icons.favorite_outline),if(allowed(farm,'tasks.view'))('tasks','Task records',Icons.task_alt),if(allowed(farm,'reproduction.view'))('reproduction_records','Reproductive records',Icons.timeline),if(allowed(farm,'breeding.observe'))('births','Birth records',Icons.child_friendly)];return RefreshIndicator(onRefresh:()async=>reload(),child:ListView(physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.all(16),children:[Text('Welcome, ${api.user?['name']??'there'}',style:TextStyle(fontSize:25,fontWeight:FontWeight.w800,color:readableText(c))),const SizedBox(height:4),const Text('Your farm at a glance'),const SizedBox(height:16),_FarmHero(farm:farm,farms:farms,select:select),const SizedBox(height:18),if(totals.isEmpty)const MessagePane('Your role has limited farm access.')else ...[Text('Farm overview',style:Theme.of(c).textTheme.titleLarge),const SizedBox(height:8),LayoutBuilder(builder:(ctx,box){final columns=box.maxWidth>=720?3:box.maxWidth>=300?2:1;final w=(box.maxWidth-12*(columns-1))/columns;return Wrap(spacing:12,runSpacing:12,children:metrics.map((m)=>SizedBox(width:w,child:Card(child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[CircleAvatar(backgroundColor:mint,foregroundColor:green,child:Icon(m.$3)),const SizedBox(height:10),Text('${totals[m.$1]??'—'}',style:TextStyle(fontSize:29,fontWeight:FontWeight.w800,color:readableText(c))),Text(m.$2)]))))).toList());}),const SizedBox(height:20),if(allowed(farm,'animals.view'))item('Farm reminders','Recorded due dates and device alerts',icon:Icons.calendar_month,onTap:()=>openPage(c,ReminderPage(api:api,farm:farm))),Text('Quick actions',style:Theme.of(c).textTheme.titleLarge),Wrap(spacing:8,runSpacing:8,children:[if(allowed(farm,'animals.create'))ActionChip(avatar:const Icon(Icons.add),label:const Text('Animal'),onPressed:()async{if(await openPage<bool>(c,AnimalForm(api:api,farm:farm))==true)reload();}),...kinds.keys.where((k)=>allowed(farm,viewPerm[k]!)).map((k)=>ActionChip(label:Text(pretty(k)),onPressed:()async{await openPage(c,CategoryPage(api:api,farm:farm,category:k));reload();}))]),const SizedBox(height:20),Text('Recent activity',style:Theme.of(c).textTheme.titleLarge),if(events.isEmpty)const MessagePane('No visible activity yet.'),...events.take(5).map((e)=>item(pretty(e['kind']),'${pretty(e['category'])} • ${shortDate(e['occurred_at'])}',icon:Icons.history,onTap:()=>eventTileOpen(c,e)))]]));});void eventTileOpen(BuildContext c,RowData e)=>openPage(c,Scaffold(appBar:AppBar(title:Text(pretty(e['kind']))),body:ListView(padding:const EdgeInsets.all(20),children:[details(Map.of(e)..removeWhere((k,v)=>['id','animal_id','author_id','payload'].contains(k))),details(obj(e['payload']??{}))])));}
/// A compact version of the web authentication hero: the original cow photo,
/// subdued by an opaque navy-to-blue overlay, with existing farm controls on top.
/// It is decorative only; figures, membership and navigation remain server-owned.
class _FarmHero extends StatelessWidget {
  const _FarmHero({required this.farm,required this.farms,required this.select});
  final RowData farm;
  final List<RowData> farms;
  final ValueChanged<String> select;

  @override Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(24),
    child: SizedBox(
      height: 225,
      child: Stack(fit:StackFit.expand,children:[
        // The same original web hero photograph, not a replacement stock image.
        Image.asset('assets/herd-hero.jpg',
          key:const Key('anirepro-cow-home'),
          fit:BoxFit.cover,alignment:Alignment.center,
          semanticLabel:'AniRepro cow on a farm'),
        // Navy glass-like treatment matching the left side of the web screenshot.
        const DecoratedBox(decoration:BoxDecoration(gradient:LinearGradient(
          begin:Alignment.centerLeft,end:Alignment.centerRight,
          colors:[Color(0xf20d2b45),Color(0xd91a4262),Color(0xc4143551)],
          stops:[0,.58,1],
        ))),
        Padding(padding:const EdgeInsets.fromLTRB(20,18,20,17),child:Column(
          crossAxisAlignment:CrossAxisAlignment.start,children:[
          Row(children:[
            Container(width:38,height:38,padding:const EdgeInsets.all(4),
              decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(10)),
              child:Image.asset('assets/logo.png',semanticLabel:'AniRepro 360 logo')),
            const SizedBox(width:10),
            const Expanded(child:Text('AniRepro 360',maxLines:1,overflow:TextOverflow.ellipsis,
              style:TextStyle(color:Colors.white,fontSize:19,fontWeight:FontWeight.w800))),
            const Icon(Icons.verified_user_outlined,color:Colors.white70,size:21),
          ]),
          const Spacer(),
          const Text('YOUR FARM WORKSPACE',style:TextStyle(
            color:Colors.white70,fontSize:11,letterSpacing:1.4,fontWeight:FontWeight.w700)),
          const SizedBox(height:5),
          DropdownButtonHideUnderline(child:DropdownButton<String>(
            value:'${farm['id']}',isExpanded:true,
            dropdownColor:navy,iconEnabledColor:Colors.white,
            style:const TextStyle(color:Colors.white,fontSize:21,fontWeight:FontWeight.w800),
            selectedItemBuilder:(context)=>farms.map((f)=>Align(
              alignment:Alignment.centerLeft,child:Text('${f['name']}',
              maxLines:1,overflow:TextOverflow.ellipsis,
              style:const TextStyle(color:Colors.white,fontSize:21,fontWeight:FontWeight.w800)))).toList(),
            items:farms.map((f)=>DropdownMenuItem<String>(value:'${f['id']}',
              child:Text('${f['name']}',maxLines:1,overflow:TextOverflow.ellipsis))).toList(),
            onChanged:(v){if(v!=null)select(v);},
          )),
          const SizedBox(height:5),
          Row(children:[const Icon(Icons.shield_outlined,size:15,color:Colors.white70),
            const SizedBox(width:6),Expanded(child:Text(pretty(farm['role']),
              maxLines:1,overflow:TextOverflow.ellipsis,
              style:const TextStyle(color:Colors.white70,fontSize:12)))]),
        ])),
      ]),
    ),
  );
}
class MorePage extends StatelessWidget{const MorePage({super.key,required this.api,required this.farm,required this.onReturnHome});final Api api;final RowData farm;final VoidCallback onReturnHome;@override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('More')),body:ListView(padding:const EdgeInsets.all(16),children:[Container(padding:const EdgeInsets.all(20),decoration:BoxDecoration(gradient:brandGradient,borderRadius:BorderRadius.circular(23)),child:Text('${farm['name']}\n${pretty(farm['role'])}',style:const TextStyle(color:Colors.white,fontSize:20,fontWeight:FontWeight.bold))),const SizedBox(height:14),Text('Clinical workspace',style:Theme.of(context).textTheme.titleLarge),const SizedBox(height:8),...kinds.keys.where((k)=>allowed(farm,viewPerm[k]!)).map((k)=>item(moduleStyles[k]!.title,moduleStyles[k]!.description,icon:moduleStyles[k]!.icon,onTap:()=>openPage(context,CategoryPage(api:api,farm:farm,category:k)))),const SizedBox(height:16),Text('Farm administration',style:Theme.of(context).textTheme.titleLarge),if(allowed(farm,'members.view'))item('Farm team','Members and invitations',icon:Icons.group_outlined,onTap:()=>openPage(context,TeamPage(api:api,farm:farm))),if(allowed(farm,'audit.view'))item('Audit history','Server-owned activity records',icon:Icons.history,onTap:()=>openPage(context,AuditPage(api:api,farm:farm))),item('Species reference','Reference profiles',icon:Icons.pets,onTap:()=>openPage(context,SpeciesPage(api:api))),const SizedBox(height:16),Text('Your account',style:Theme.of(context).textTheme.titleLarge),item('Sync center','Offline records and synchronization',icon:Icons.cloud_sync_outlined,onTap:()=>openPage(context,SyncPage(api:api,farm:farm))),if(allowed(farm,'animals.view'))item('Farm reminders','Recorded dates, estimates and native alerts',icon:Icons.calendar_month,onTap:()=>openPage(context,ReminderPage(api:api,farm:farm))),item('Notifications','Farm updates',icon:Icons.notifications_none,onTap:()=>openPage(context,NotificationsPage(api:api))),item('Profile & settings','Account and memberships',icon:Icons.settings_outlined,onTap:()async{await openPage(context,SettingsPage(api:api));onReturnHome();})]));}
