import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../core/api.dart';
class BrandButton extends StatelessWidget {
  const BrandButton(this.label,{super.key,this.action,this.busy=false}); final String label;final VoidCallback? action;final bool busy;
  @override Widget build(BuildContext context)=>DecoratedBox(decoration:BoxDecoration(gradient:action==null&&!busy?null:brandGradient,color:action==null&&!busy?navy.withValues(alpha:.35):null,borderRadius:BorderRadius.circular(32)),child:FilledButton(onPressed:busy?null:action,style:FilledButton.styleFrom(backgroundColor:Colors.transparent,disabledBackgroundColor:Colors.transparent,shadowColor:Colors.transparent),child:SizedBox(width:double.infinity,child:Center(child:AnimatedSwitcher(duration:const Duration(milliseconds:220),child:busy?const SizedBox(width:24,height:24,child:CircularProgressIndicator(strokeWidth:2.5,color:Colors.white)):Text(label,style:const TextStyle(fontWeight:FontWeight.w700,fontSize:16,color:Colors.white)))))));
}
class Loading extends StatelessWidget {const Loading({super.key});@override Widget build(BuildContext context)=>const Center(child:Padding(padding:EdgeInsets.all(32),child:Column(mainAxisSize:MainAxisSize.min,children:[CircularProgressIndicator(color:green),SizedBox(height:14),Text('Loading your workspace…')])));}
class MessagePane extends StatelessWidget {const MessagePane(this.message,{super.key,this.retry,this.icon=Icons.info_outline});final String message;final VoidCallback? retry;final IconData icon;@override Widget build(BuildContext context)=>Center(child:Padding(padding:const EdgeInsets.all(24),child:Column(mainAxisSize:MainAxisSize.min,children:[Icon(icon,size:42,color:green),const SizedBox(height:12),Text(message,textAlign:TextAlign.center),if(retry!=null)TextButton.icon(onPressed:retry,icon:const Icon(Icons.refresh),label:const Text('Try again'))])));}
void toast(BuildContext c,Object msg)=>ScaffoldMessenger.of(c).showSnackBar(SnackBar(content:Text('$msg')));
Future<bool> confirm(BuildContext c,String message)async=>await showDialog<bool>(context:c,builder:(ctx)=>AlertDialog(title:const Text('Confirm action'),content:Text(message),actions:[TextButton(onPressed:()=>Navigator.pop(ctx,false),child:const Text('Cancel')),FilledButton(onPressed:()=>Navigator.pop(ctx,true),child:const Text('Confirm'))]))??false;
Future<T?> openPage<T>(BuildContext c,Widget page)=>Navigator.of(c).push<T>(MaterialPageRoute(builder:(_)=>page));
class DataPage extends StatefulWidget {const DataPage({super.key,required this.title,required this.load,required this.content,this.actions});final String title;final Future<dynamic> Function() load;final Widget Function(BuildContext,dynamic,VoidCallback) content;final List<Widget>? actions;@override State<DataPage> createState()=>_DataPageState();}
class _DataPageState extends State<DataPage> {
  late Future<dynamic> data;
  @override void initState() { super.initState(); data = widget.load(); }
  void reload() { if (mounted) setState(() => data = widget.load()); }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title), actions: [
      ...?widget.actions, IconButton(onPressed: reload, icon: const Icon(Icons.refresh), tooltip: 'Refresh'),
    ]),
    body: FutureBuilder<dynamic>(future: data, builder: (c, s) {
      final waiting = s.connectionState != ConnectionState.done;
      if (waiting && !s.hasData) return const Loading();
      if (s.hasError) return MessagePane('${s.error}', retry: reload, icon: Icons.cloud_off_outlined);
      return Stack(fit: StackFit.expand, children: [
        // Retain the current view while a same-page refresh runs, without
        // permitting actions against data that is being refreshed.
        AbsorbPointer(absorbing: waiting, child: widget.content(c, s.data, reload)),
        if (waiting) const Align(alignment: Alignment.topCenter, child: LinearProgressIndicator(minHeight: 3)),
      ]);
    }),
  );
}
Widget item(String title,String subtitle,{IconData icon=Icons.chevron_right,VoidCallback? onTap,Widget? trailing})=>Card(child:ListTile(leading:CircleAvatar(backgroundColor:mint,foregroundColor:green,child:Icon(icon)),title:Text(title,style:const TextStyle(fontWeight:FontWeight.w600)),subtitle:Text(subtitle),trailing:trailing??(onTap==null?null:const Icon(Icons.chevron_right)),onTap:onTap));
Widget details(RowData data)=>Column(crossAxisAlignment:CrossAxisAlignment.start,children:data.entries.where((e)=>e.value!=null&&e.value!='').map((e)=>Padding(padding:const EdgeInsets.symmetric(vertical:5),child:Text('${pretty(e.key)}: ${pretty(e.value)}'))).toList());
