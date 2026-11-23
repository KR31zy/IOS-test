import 'dart:io';
import 'dart:typed_data';
import '../core/appearance.dart';
import '../core/profile_photo.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import '../core/api.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'records.dart';
import '../features/reminders/push_service.dart';
import '../features/analytics/report_data.dart';
import '../features/analytics/report_charts.dart';
Future<void> shareProtected(BuildContext c,Api api,String path,String filename)async{Directory? dir;try{final r=await api.download(path);dir=await (await getTemporaryDirectory()).createTemp('anirepro_');final safe=filename.replaceAll(RegExp(r'[^a-zA-Z0-9._-]'),'_');final f=File('${dir.path}/${safe.isEmpty?'record':safe}');await f.writeAsBytes(r.bodyBytes,flush:true);if(!c.mounted)return;final box=c.findRenderObject();await Share.shareXFiles([XFile(f.path)],sharePositionOrigin:box is RenderBox?box.localToGlobal(Offset.zero)&box.size:null);}catch(e){if(c.mounted)toast(c,e);}finally{try{await dir?.delete(recursive:true);}catch(_){}}}
class AttachmentsPage extends StatefulWidget{const AttachmentsPage({super.key,required this.api,required this.farm,required this.animal,this.eventId});final Api api;final RowData farm,animal;final String? eventId;@override State<AttachmentsPage> createState()=>_AttachmentsPageState();}
class _AttachmentsPageState extends State<AttachmentsPage>{bool busy=false;String get path=>'${animalPath(widget.farm,widget.animal)}/attachments';Future<void> upload(VoidCallback reload)async{setState(()=>busy=true);try{final picked=await FilePicker.platform.pickFiles(type:FileType.custom,allowedExtensions:['pdf','png','jpg','jpeg']);if(picked==null)return;final f=picked.files.single;if(f.path==null||f.size<=0||f.size>10*1024*1024)throw Exception('Choose a nonempty PDF, PNG or JPEG up to 10 MiB.');final ext=f.extension?.toLowerCase();await widget.api.upload(path,f.path!,f.name,ext=='pdf'?'application/pdf':ext=='png'?'image/png':'image/jpeg',eventId:widget.eventId);reload();}catch(e){if(mounted)toast(context,e);}finally{if(mounted)setState(()=>busy=false);}}@override Widget build(BuildContext context)=>DataPage(title:'Evidence',load:()=>widget.api.get(path),content:(c,data,reload){final files=rows(data).where((a)=>widget.eventId==null||a['event_id']==widget.eventId).toList();return ListView(padding:const EdgeInsets.all(16),children:[if(allowed(widget.farm,'evidence.create'))BrandButton('Upload evidence',busy:busy,action:()=>upload(reload)),const Padding(padding:EdgeInsets.all(12),child:Text('PDF, PNG or JPEG • 10 MiB maximum. Protect clinical files when sharing.')),if(files.isEmpty)const MessagePane('No evidence attached.'),...files.map((f)=>item('${f['name']}','${(f['byte_size'] as num? ?? 0)/1024 ~/ 1} KB • ${shortDate(f['created_at'])}',icon:Icons.insert_drive_file_outlined,onTap:()=>shareProtected(c,widget.api,'$path/${f['id']}/download','${f['name']}'),trailing:IconButton(tooltip:'Download / share',icon:const Icon(Icons.download),onPressed:()=>shareProtected(c,widget.api,'$path/${f['id']}/download','${f['name']}'))))]);});}
class CyclePage extends StatelessWidget{const CyclePage({super.key,required this.api,required this.farm,required this.animal});final Api api;final RowData farm,animal;@override Widget build(BuildContext context)=>DataPage(title:'Cycle analysis',load:()=>api.get('${animalPath(farm,animal)}/cycle-summary'),content:(c,data,reload){final r=obj(data);final values=(r['interval_days'] is List ? (r['interval_days'] as List).whereType<num>().toList() : <num>[]);return ListView(padding:const EdgeInsets.all(18),children:[Text('${animal['name']}',style:Theme.of(c).textTheme.headlineSmall),const SizedBox(height:12),Card(child:Padding(padding:const EdgeInsets.all(18),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('Estimated next estrus · not clinically confirmed'),Text(pretty(r['estimated_next_estrus']),style:const TextStyle(fontSize:28,fontWeight:FontWeight.bold,color:green)),Text(pretty(r['estimate_status'])),Text('Based on ${r['supporting_cycles'] ?? 0} recent observed cycle intervals'),Text('${r['warning']}')]))),Text('Observed cycle intervals',style:Theme.of(c).textTheme.titleLarge),if(values.isEmpty)const MessagePane('Insufficient observations for a cycle chart.')else ...values.asMap().entries.map((e)=>BarLine('Cycle ${e.key+1}',e.value,values.reduce((a,b)=>a>b?a:b),suffix:' days')),details(Map.of(r)..removeWhere((k,v)=>['animal_id','reference_profile','interval_days','warning','estimated_next_estrus','estimate_status'].contains(k)))]);});}
class BarLine extends StatelessWidget{const BarLine(this.label,this.value,this.max,{super.key,this.suffix=''});final String label,suffix;final num value,max;@override Widget build(BuildContext context)=>Padding(padding:const EdgeInsets.symmetric(vertical:8),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Row(children:[Expanded(child:Text(label)),Text('$value$suffix',style:const TextStyle(fontWeight:FontWeight.bold))]),const SizedBox(height:6),ClipRRect(borderRadius:BorderRadius.circular(12),child:TweenAnimationBuilder<double>(duration:MediaQuery.disableAnimationsOf(context)?Duration.zero:const Duration(milliseconds:650),tween:Tween(begin:0,end:max>0?(value/max).clamp(0,1).toDouble():0),builder:(c,v,_)=>LinearProgressIndicator(value:v,minHeight:12,color:green,backgroundColor:mint)))]));}
class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key, required this.api, required this.farm});
  final Api api;
  final RowData farm;
  @override State<ReportsPage> createState() => _ReportsPageState();
}
class _ReportsPageState extends State<ReportsPage> {
  String category = 'all';
  String? compareFirst;
  String? compareSecond;
  bool exporting = false;
  Future<void> export(BuildContext context, String format) async {
    if (exporting) return;
    setState(() => exporting = true);
    try {
      await shareProtected(context, widget.api, '${farmPath(widget.farm)}/reports/$format', 'anirepro-report.$format');
    } finally {
      if (mounted) setState(() => exporting = false);
    }
  }
  Widget panel(String title, List<Widget> children) => Card(child: Padding(
    padding: const EdgeInsets.all(18), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(title, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 19, color: Theme.of(context).colorScheme.onSurface)),
      const SizedBox(height: 12), ...children,
    ]),
  ));
  @override Widget build(BuildContext context) => DataPage(
    title: 'Reports & analytics',
    load: () async => Future.wait([
      widget.api.get('${farmPath(widget.farm)}/summary'),
      widget.api.get('${farmPath(widget.farm)}/animals'),
      widget.api.get('${farmPath(widget.farm)}/events'),
    ]),
    content: (c, data, reload) {
      final summary = obj(data[0]);
      final report = ReportData(rows(data[2]), rows(data[1]));
      final categories = report.categories;
      final available = report.events.map((e) => e['category']).whereType<String>().toSet().toList()..sort();
      final filter = available.contains(category) ? category : 'all';
      final buckets = report.monthly(DateTime.now(), category: filter == 'all' ? null : filter);
      return ListView(padding: const EdgeInsets.all(16), children: [
        Text('${widget.farm['name']}', style: Theme.of(c).textTheme.headlineSmall),
        const Text('Live farm data • role-filtered records'),
        const SizedBox(height: 12),
        if (allowed(widget.farm, 'reports.export')) Wrap(spacing: 8, children: [
          OutlinedButton.icon(onPressed: exporting ? null : () => export(c, 'pdf'), icon: const Icon(Icons.picture_as_pdf), label: const Text('Export PDF')),
          OutlinedButton.icon(onPressed: exporting ? null : () => export(c, 'csv'), icon: const Icon(Icons.table_chart), label: const Text('Export CSV')),
        ]),
        if (exporting) const LinearProgressIndicator(),
        panel('Farm totals', [
          ...summary.entries.where((e) => e.value is num).map((e) => ListTile(dense: true, contentPadding: EdgeInsets.zero,
            title: Text(pretty(e.key)), trailing: Text('${e.value}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)))),
          const Text('Confirmed pregnancies counts animals with historical confirmation records, not necessarily current pregnancies.'),
        ]),
        panel('Animals by species', [SpeciesDonut(counts: report.species)]),
        panel('Monthly record activity', [
          DropdownButtonFormField<String>(key: ValueKey(filter), initialValue: filter, isExpanded: true,
            decoration: const InputDecoration(labelText: 'Record category'),
            items: [const DropdownMenuItem(value: 'all', child: Text('All visible records')), ...available.map((v) => DropdownMenuItem(value:v, child: Text(pretty(v))))],
            onChanged: (v) => setState(() => category = v ?? 'all')),
          const SizedBox(height: 12),
          if (buckets.every((b) => b.count == 0)) const Text('No returned records in this period.') else MonthlyChart(buckets: buckets),
          const SizedBox(height: 8),
          Text(report.possiblyCapped ? 'Partial history: the server returns at most 500 visible records. Earlier monthly counts may be incomplete.' : 'Based on the visible records returned by the server.'),
        ]),
        if (available.length >= 2) panel('Compare monthly activity', [
          const Text('Compare two recorded activity categories over the same six months.'),
          const SizedBox(height:12),
          DropdownButtonFormField<String>(
            key:ValueKey('first-${compareFirst ?? available.first}'),
            initialValue:available.contains(compareFirst)?compareFirst:available.first,
            decoration:const InputDecoration(labelText:'First category'),
            isExpanded:true,
            items:available.map((v)=>DropdownMenuItem(value:v,child:Text(pretty(v)))).toList(),
            onChanged:(v)=>setState(()=>compareFirst=v),
          ),
          const SizedBox(height:10),
          DropdownButtonFormField<String>(
            key:ValueKey('second-${compareSecond ?? available[1]}'),
            initialValue:available.contains(compareSecond)?compareSecond:available[1],
            decoration:const InputDecoration(labelText:'Second category'),
            isExpanded:true,
            items:available.map((v)=>DropdownMenuItem(value:v,child:Text(pretty(v)))).toList(),
            onChanged:(v)=>setState(()=>compareSecond=v),
          ),
          const SizedBox(height:14),
          Builder(builder:(context){
            final first=available.contains(compareFirst)?compareFirst!:available.first;
            final second=available.contains(compareSecond)?compareSecond!:available[1];
            if(first==second)return const Text('Choose two different record categories.');
            return ComparisonMonthlyChart(buckets:report.compareMonthly(DateTime.now(),first:first,second:second),
              firstLabel:pretty(first),secondLabel:pretty(second));
          }),
        ]) else panel('Compare monthly activity', [
          const Text('Record at least two different activity categories to enable comparison charts.'),
        ]),
        panel('Previous versus recent activity', [
          const Text('Compare recorded events for two consecutive three-month periods.'),
          const SizedBox(height:10),
          PeriodComparisonChart(counts:report.compareThreeMonthPeriods(DateTime.now(),available.take(5))
            .map((key,value)=>MapEntry(pretty(key),value))),
        ]),
        panel('Visible record distribution', [
          if (categories.isEmpty) const Text('No clinical records.'),
          ...categories.entries.map((e) => BarLine(e.key, e.value, report.events.length)),
          Text('${report.events.length} returned records • maximum 500'),
        ]),
      ]);
    },
  );
}
class NotificationsPage extends StatelessWidget{const NotificationsPage({super.key,required this.api});final Api api;@override Widget build(BuildContext context)=>DataPage(title:'Notifications',actions:[IconButton(tooltip:'Remote push settings',onPressed:()=>openPage(context,PushSettingsPage(api:api)),icon:const Icon(Icons.settings_outlined))],load:()=>api.get('/api/notifications'),content:(c,data,reload){final n=obj(data);final items=rows(n['items']);Future<void> change(String method,String path)async{try{await api.request(method,path);reload();}catch(e){if(c.mounted)toast(c,e);}}return ListView(padding:const EdgeInsets.all(16),children:[Text('${n['unread_count']} unread',style:Theme.of(c).textTheme.titleLarge),TextButton(onPressed:()=>change('PATCH','/api/notifications/read-all'),child:const Text('Mark all as read')),if(items.isEmpty)const MessagePane('You are all caught up.'),...items.map((x)=>item('${x['title']}','${x['message']}\n${pretty(x['farm_name'])} • ${shortDate(x['created_at'])}',icon:x['read_at']==null?Icons.notifications_active:Icons.notifications_none,onTap:()=>change('PATCH','/api/notifications/${x['id']}/read'),trailing:IconButton(tooltip:'Dismiss',icon:const Icon(Icons.close),onPressed:()=>change('DELETE','/api/notifications/${x['id']}'))))]);});}
class TeamPage extends StatefulWidget{const TeamPage({super.key,required this.api,required this.farm});final Api api;final RowData farm;@override State<TeamPage> createState()=>_TeamPageState();}
class _TeamPageState extends State<TeamPage>{bool busy=false;String get path=>farmPath(widget.farm);Future<void> invite(VoidCallback reload)async{final email=TextEditingController();String role='farmer';try{final result=await showDialog<RowData>(context:context,builder:(ctx)=>StatefulBuilder(builder:(ctx,set)=>AlertDialog(title:const Text('Invite farm member'),content:Column(mainAxisSize:MainAxisSize.min,children:[TextField(controller:email,keyboardType:TextInputType.emailAddress,decoration:const InputDecoration(labelText:'Email address')),const SizedBox(height:12),DropdownButtonFormField<String>(initialValue:role,items:['farmer','breeder','veterinarian','researcher'].map((r)=>DropdownMenuItem(value:r,child:Text(pretty(r)))).toList(),onChanged:(v)=>set(()=>role=v!))]),actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Cancel')),FilledButton(onPressed:()=>Navigator.pop(ctx,{'email':email.text.trim(),'role':role}),child:const Text('Invite'))])));if(result==null)return;setState(()=>busy=true);final r=obj(await widget.api.post('$path/invitations',result));reload();if(!mounted)return;if(r['invitation_url']!=null){await showDialog<void>(context:context,builder:(c)=>AlertDialog(title:const Text('Private invitation'),content:SelectableText('${r['invitation_url']}'),actions:[TextButton(onPressed:()async{await Clipboard.setData(ClipboardData(text:'${r['invitation_url']}'));if(c.mounted)Navigator.pop(c);},child:const Text('Copy link'))]));}else{toast(context,r['message']??'Invitation sent');}}catch(e){if(mounted)toast(context,e);}finally{email.dispose();if(mounted)setState(()=>busy=false);}}
Future<void> mutate(String method,String suffix,VoidCallback reload,{RowData? body})async{if(busy)return;setState(()=>busy=true);try{await widget.api.request(method,'$path/$suffix',body:body);reload();}catch(e){if(mounted)toast(context,e);}finally{if(mounted)setState(()=>busy=false);}}
@override Widget build(BuildContext context)=>DataPage(title:'Farm team',load:()async=>Future.wait([widget.api.get('$path/members'),widget.api.get('$path/invitations')]),content:(c,data,reload)=>ListView(padding:const EdgeInsets.all(16),children:[if(allowed(widget.farm,'members.invite'))BrandButton('Invite member',busy:busy,action:()=>invite(reload)),const SizedBox(height:14),Text('Members',style:Theme.of(c).textTheme.titleLarge),...rows(data[0]).map((m)=>item('${m['name']}','${m['email']} • ${pretty(m['role'])}',icon:Icons.person_outline,trailing: PopupMenuButton<String>(enabled:!busy,itemBuilder:(_)=>[if(allowed(widget.farm,'members.update_role'))...['farm_manager','farmer','breeder','veterinarian','researcher'].map((r)=>PopupMenuItem(value:r,child:Text('Set ${pretty(r)}'))),if(allowed(widget.farm,'members.remove'))const PopupMenuItem(value:'remove',child:Text('Remove member'))],onSelected:(v)async{if(!await confirm(c,v=='remove'?'Remove this farm member?':'Change this member’s role to ${pretty(v)}?'))return;await mutate(v=='remove'?'DELETE':'PATCH','members/${m['id']}',reload,body:v=='remove'?null:{'role':v});}))),Text('Pending invitations',style:Theme.of(c).textTheme.titleLarge),if(rows(data[1]).isEmpty)const MessagePane('No pending invitations.'),...rows(data[1]).map((m)=>item('${m['email']}','${pretty(m['role'])} • ${m['expired']==true?'Expired':'Pending'}',icon:Icons.mail_outline,trailing:IconButton(tooltip:'Revoke',onPressed:busy?null:()async{if(await confirm(c,'Revoke this invitation?'))await mutate('DELETE','invitations/${m['id']}',reload);},icon:const Icon(Icons.close))))]));}
class SettingsPage extends StatefulWidget{const SettingsPage({super.key,required this.api});final Api api;@override State<SettingsPage> createState()=>_SettingsPageState();}
class _SettingsPageState extends State<SettingsPage> {
  bool busy=false, photoBusy=false;
  Uint8List? profilePhoto;
  @override void initState(){super.initState();_loadProfilePhoto();}
  Future<void> _loadProfilePhoto() async {
    final id='${widget.api.user?['id']??''}';
    if(id.isEmpty)return;
    try {
      final bytes=await ProfilePhotoStore.load(widget.api.base,id);
      if(mounted)setState(()=>profilePhoto=bytes);
    } catch (_) {
      // A damaged local image must not prevent access to the account screen.
      if(mounted)setState(()=>profilePhoto=null);
    }
  }
  Future<void> chooseProfilePhoto()async{
    if(photoBusy)return;
    setState(()=>photoBusy=true);
    try{
      final result=await FilePicker.platform.pickFiles(type:FileType.image,withData:true);
      if(result==null)return;
      final file=result.files.single;
      if(file.size<=0||file.size>ProfilePhotoStore.maxBytes){
        throw ArgumentError('Choose a photo smaller than 2 MB.');
      }
      final bytes=file.bytes??(file.path==null?null:await File(file.path!).readAsBytes());
      if(bytes==null||!ProfilePhotoStore.supportedImage(bytes)){
        throw ArgumentError('Choose a valid JPEG or PNG image smaller than 2 MB.');
      }
      final id='${widget.api.user?['id']??''}';
      if(id.isEmpty)throw StateError('Sign in to set a profile photo.');
      await ProfilePhotoStore.save(widget.api.base,id,bytes);
      if(mounted)setState(()=>profilePhoto=bytes);
    }catch(e){if(mounted)toast(context,e);}
    finally{if(mounted)setState(()=>photoBusy=false);}
  }
  Future<void> removePhoto()async {
    final id='${widget.api.user?['id']??''}';
    if(id.isEmpty||!await confirm(context,'Remove your profile photo from this device?'))return;
    try {await ProfilePhotoStore.remove(widget.api.base,id);if(mounted)setState(()=>profilePhoto=null);}
    catch(e){if(mounted)toast(context,e);}
  }
  Future<void> setUsername(BuildContext c,VoidCallback reload)async{
    final name=TextEditingController();
    try{
      final value=await showDialog<String>(context:c,builder:(ctx)=>AlertDialog(
        title:const Text('Choose username'),
        content:TextField(controller:name,decoration:const InputDecoration(labelText:'Username (3–32 characters)')),
        actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Cancel')),
          FilledButton(onPressed:()=>Navigator.pop(ctx,name.text.trim()),child:const Text('Save'))]));
      if(value==null)return;
      setState(()=>busy=true);
      await widget.api.request('PATCH','/api/auth/username',body:{'username':value});reload();
    }catch(e){if(c.mounted)toast(c,e);}
    finally{name.dispose();if(mounted)setState(()=>busy=false);}
  }
  Widget appearanceSelector(BuildContext c)=>Card(child:Padding(padding:const EdgeInsets.all(17),child:Column(
    crossAxisAlignment:CrossAxisAlignment.start,children:[
      Text('Appearance',style:Theme.of(c).textTheme.titleMedium?.copyWith(fontWeight:FontWeight.w700)),
      const SizedBox(height:6),
      Text('Follow the phone setting or choose a mode for AniRepro.',style:Theme.of(c).textTheme.bodySmall),
      const SizedBox(height:10),
      ValueListenableBuilder<ThemeMode>(valueListenable:AppAppearance.instance,builder:(ctx,current,_)=>Wrap(
        spacing:9,runSpacing:6,children:[
          for(final mode in ThemeMode.values)ChoiceChip(
            avatar:Icon(switch(mode){ThemeMode.system=>Icons.settings_suggest_outlined,ThemeMode.light=>Icons.light_mode_outlined,ThemeMode.dark=>Icons.dark_mode_outlined},size:17),
            label:Text(switch(mode){ThemeMode.system=>'Device default',ThemeMode.light=>'Light',ThemeMode.dark=>'Dark'}),
            selected:current==mode,
            onSelected:(selected)async {if(!selected)return;try{await AppAppearance.instance.choose(mode);}catch(e){if(ctx.mounted)toast(ctx,e);}},
          ),
        ])),
    ])));
  @override Widget build(BuildContext context)=>DataPage(title:'My profile',load:()=>widget.api.get('/api/me'),content:(c,data,reload){
    final me=obj(data);
    return ListView(padding:const EdgeInsets.all(18),children:[
      Center(child:Stack(clipBehavior:Clip.none,children:[
        CircleAvatar(radius:50,backgroundColor:mint,foregroundColor:green,
          backgroundImage:profilePhoto==null?null:MemoryImage(profilePhoto!),
          child:profilePhoto==null?const Icon(Icons.person,color:green,size:49):null),
        Positioned(right:-2,bottom:-3,child:CircleAvatar(radius:19,backgroundColor:Theme.of(c).colorScheme.primary,
          child:IconButton(icon:const Icon(Icons.camera_alt_outlined,size:18,color:Colors.white),
            tooltip:'Choose profile photo',onPressed:photoBusy?null:chooseProfilePhoto))),
      ])),
      const SizedBox(height:12),
      Center(child:Text('${me['name']}',style:Theme.of(c).textTheme.headlineSmall)),
      Center(child:Text('${me['email']}')),
      const SizedBox(height:8),
      Center(child:Wrap(alignment:WrapAlignment.center,spacing:10,children:[
        TextButton.icon(onPressed:photoBusy?null:chooseProfilePhoto,
          icon:const Icon(Icons.add_a_photo_outlined),label:Text(photoBusy?'Opening photos…':'Choose photo from phone')),
        if(profilePhoto!=null)TextButton(onPressed:photoBusy?null:removePhoto,child:const Text('Remove photo')),
      ])),
      Center(child:Text('Encrypted on this device; profile photos do not yet sync with other devices.',
        textAlign:TextAlign.center,style:Theme.of(c).textTheme.bodySmall)),
      if(Api.usernameMode)ListTile(title:Text('Username: ${pretty(me['username'])}'),
        trailing:TextButton(onPressed:busy?null:()=>setUsername(c,reload),child:const Text('Change'))),
      const Divider(),
      Text('Farm memberships',style:Theme.of(c).textTheme.titleLarge),
      ...rows(me['farms']).map((f)=>item('${f['name']}',pretty(f['role']),icon:Icons.agriculture)),
      const SizedBox(height:12),
      appearanceSelector(c),
      const SizedBox(height:12),
      const Text('Accounts and roles are managed by the shared server.'),
      const Text('AniRepro 360 • Mobile 2.4'),
      const SizedBox(height:16),
      OutlinedButton.icon(onPressed:busy?null:()async{
        if(widget.api.pending.isNotEmpty&&!await confirm(c,
          'Pending records remain encrypted on this device and can only be recovered by signing in to the same account online. Sign out?'))return;
        try{await PushService.instance.disable(widget.api);await widget.api.logout();}
        catch(e){if(c.mounted)toast(c,e);}
      },icon:const Icon(Icons.logout),label:const Text('Sign out')),
    ]);
  });
}
class SpeciesPage extends StatelessWidget{const SpeciesPage({super.key,required this.api});final Api api;@override Widget build(BuildContext context)=>DataPage(title:'Species reference',load:()=>api.get('/api/species/profiles'),content:(c,data,reload)=>ListView(padding:const EdgeInsets.all(16),children:[const Text('Reference profiles are not clinically validated.'),...obj(data).entries.map((e)=>Card(child:ExpansionTile(title:Text(pretty(e.key)),leading:const Icon(Icons.pets,color:green),children:[Padding(padding:const EdgeInsets.all(16),child:details(obj(e.value)))]))) ]));}
class AuditPage extends StatelessWidget{const AuditPage({super.key,required this.api,required this.farm});final Api api;final RowData farm;@override Widget build(BuildContext context)=>DataPage(title:'Audit history',load:()=>api.get('${farmPath(farm)}/audit'),content:(c,data,reload)=>ListView(padding:const EdgeInsets.all(16),children:[if(rows(data).isEmpty)const MessagePane('No audit entries.'),...rows(data).map((r)=>item(pretty(r['action']),shortDate(r['at']),icon:Icons.history,onTap:()=>showDialog<void>(context:c,builder:(ctx)=>AlertDialog(title:const Text('Audit entry'),content:details(r),actions:[TextButton(onPressed:()=>Navigator.pop(ctx),child:const Text('Close'))])))) ]));}
