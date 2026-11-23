import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/theme.dart';
import '../../screens/records.dart';
import '../../widgets/common.dart';
import 'store.dart';

class SyncBanner extends StatelessWidget {
  const SyncBanner({super.key,required this.api,required this.open});
  final Api api;
  final VoidCallback open;
  @override Widget build(BuildContext context) => ValueListenableBuilder<int>(
    valueListenable:api.syncSignal,builder:(c,_,child){
      if(!api.signedIn||(!api.offline&&!api.usedOffline&&api.pending.isEmpty&&api.syncIssue==null))return const SizedBox.shrink();
      final label=api.offline?'Offline • saved views only':api.pending.isNotEmpty?'${api.pending.length} pending • open Sync center':api.syncIssue!=null?'Sync needs attention':'Reconnected • refresh saved views';
      return Material(color:api.offline?const Color(0xffffefd2):mint,child:SafeArea(bottom:false,child:InkWell(onTap:open,child:Padding(padding:const EdgeInsets.symmetric(horizontal:16,vertical:10),child:Row(children:[Icon(api.offline?Icons.cloud_off:Icons.cloud_sync_outlined,color:navy,size:20),const SizedBox(width:10),Expanded(child:Text(label,style:const TextStyle(color:navy,fontWeight:FontWeight.w600))),if(api.syncing)const SizedBox(width:16,height:16,child:CircularProgressIndicator(strokeWidth:2))else const Icon(Icons.chevron_right,color:navy)])))));
    });
}

class SyncPage extends StatefulWidget {
  const SyncPage({super.key,required this.api,this.farm});
  final Api api;
  final RowData? farm;
  @override State<SyncPage> createState()=>_SyncPageState();
}
class _SyncPageState extends State<SyncPage>{
  bool preparing=false;
  String? notice;
  Future<void> prepare()async{
    final farm=widget.farm;
    if(farm==null||widget.api.offline)return;
    setState((){preparing=true;notice=null;});
    var count=0;
    try{
      final api=widget.api;
      final id=farmPath(farm);
      final memberships=rows(await api.get('/api/farms'));
      final current=memberships.where((r)=>r['id']==farm['id']).firstOrNull;
      if(current==null)throw ApiError(403,'Farm membership is no longer available.');
      final paths=<String>[
        if(allowed(current,'dashboard.view'))'$id/summary',
        if(allowed(current,'animals.view'))'$id/animals',
        if(allowed(current,'animals.view'))'$id/events',
        ...viewPerm.entries.where((e)=>allowed(current,e.value)).map((e)=>'$id/events?category=${e.key}'),
        '/api/species/profiles', '/api/me',
      ];
      for(final path in paths){
        if(!mounted||api.offline)break;
        await api.get(path);if(api.offline)break;count++;
      }
      if(mounted)setState(()=>notice='Refreshed $count of ${paths.length} core views. Open individual animal histories while connected to cache them too.');
    }catch(e){if(mounted)setState(()=>notice='Refreshed $count views. $e');}
    finally{if(mounted)setState(()=>preparing=false);}
  }
  String label(PendingWrite p)=>p.path.endsWith('/events')?'${pretty(p.body['category'])} • ${pretty(p.body['kind'])}':'Register ${pretty(p.body['name'])}';
  @override Widget build(BuildContext context)=>ValueListenableBuilder<int>(valueListenable:widget.api.syncSignal,builder:(c,_,child){
    final api=widget.api;
    final pending=api.pending;
    return Scaffold(appBar:AppBar(title:const Text('Sync center')),body:ListView(padding:const EdgeInsets.all(16),children:[
      Container(padding:const EdgeInsets.all(20),decoration:BoxDecoration(gradient:brandGradient,borderRadius:BorderRadius.circular(24)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Icon(api.offline?Icons.cloud_off:Icons.cloud_done_outlined,color:Colors.white,size:36),const SizedBox(height:12),Text(api.offline?'Working offline':'Server synchronization',style:const TextStyle(fontSize:24,color:Colors.white,fontWeight:FontWeight.w800)),Text('${pending.length} pending • ${pending.where((p)=>p.blocked).length} need review',style:const TextStyle(color:Colors.white70))])),
      if(api.lastSyncAt!=null)Padding(padding:const EdgeInsets.only(top:8),child:Text('Last completed sync: ${shortDate(api.lastSyncAt!.toIso8601String())}')),
      const SizedBox(height:16),
      const Text('Saved views are snapshots, not live records. Pending entries are not included in confirmed server totals. Sign in online periodically; offline access never extends the server session.'),
      const SizedBox(height:12),BrandButton('Sync now',busy:api.syncing,action:api.canSync&&!preparing?()async{await api.synchronize();}:null),
      if(api.syncIssue!=null)Padding(padding:const EdgeInsets.symmetric(vertical:8),child:Text(api.syncIssue!,style:TextStyle(color:Theme.of(c).colorScheme.error))),
      if(widget.farm!=null)...[const SizedBox(height:12),OutlinedButton.icon(onPressed:api.offline||preparing||api.syncing?null:prepare,icon:preparing?const SizedBox(width:16,height:16,child:CircularProgressIndicator(strokeWidth:2)):const Icon(Icons.download_for_offline_outlined),label:const Text('Prepare this farm for offline use'))],
      if(notice!=null)Padding(padding:const EdgeInsets.symmetric(vertical:8),child:Text(notice!)),
      const SizedBox(height:16),Text('Pending submissions',style:Theme.of(c).textTheme.titleLarge),
      if(pending.isEmpty)const MessagePane('No pending submissions.',icon:Icons.cloud_done_outlined),
      for(final p in pending)Card(child:ExpansionTile(leading:Icon(p.blocked?Icons.error_outline:Icons.schedule,color:p.blocked?Theme.of(c).colorScheme.error:green),title:Text(label(p)),subtitle:Text('${p.blocked?'Needs review':'Pending'} • ${shortDate(p.createdAt)}'),children:[Padding(padding:const EdgeInsets.all(16),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('Farm: ${p.path.split('/')[3]}'),Text('Attempts: ${p.attempts}'),if(p.issue!=null)Text(p.issue!),const SizedBox(height:8),details(p.body),const SizedBox(height:12),Wrap(spacing:8,children:[OutlinedButton(onPressed:api.syncing||preparing?null:()async{try{await api.retryPending(p.key);}catch(e){if(c.mounted)toast(c,e);}},child:const Text('Retry same record')),TextButton(onPressed:api.syncing||preparing?null:()async{if(!await confirm(c,'Remove this pending entry from this phone? It may already exist on the server if a response was lost. Check the server before recording it again.'))return;try{await api.discardPending(p.key);}catch(e){if(c.mounted)toast(c,e);}},child:const Text('Discard local entry'))])]))])),
      const SizedBox(height:12),const Text('Attachments, account changes, team administration and exports require internet. After synchronization, refresh your farm screens to load confirmed records. Newly registered offline animals can receive clinical records after their server IDs are available.'),
    ]));
  });
}
