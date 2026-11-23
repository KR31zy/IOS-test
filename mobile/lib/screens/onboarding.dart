import 'package:flutter/material.dart';
import '../core/theme.dart';

/// An informational introduction for first-time, signed-out users only.
/// Uses the existing AniRepro logo and brand colors, not an alternate identity.
class OnboardingPage extends StatelessWidget {
  const OnboardingPage({super.key, required this.onGetStarted});
  final Future<void> Function() onGetStarted;

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    return Scaffold(body: SafeArea(child: LayoutBuilder(builder:(context, constraints) =>
      SingleChildScrollView(child: ConstrainedBox(
        constraints: BoxConstraints(minHeight: constraints.maxHeight),
        child: Padding(padding: const EdgeInsets.fromLTRB(24,20,24,28), child: Column(
          crossAxisAlignment:CrossAxisAlignment.stretch,children:[
            const Text('WELCOME TO ANIREPRO 360',style:TextStyle(color:green,fontWeight:FontWeight.w800,letterSpacing:1.5,fontSize:12)),
            const SizedBox(height:18),
            ClipRRect(borderRadius:BorderRadius.circular(30),child:SizedBox(height:210,
              child:Stack(alignment:Alignment.center,children:[
                Positioned.fill(child:Image.asset('assets/herd-hero.jpg',fit:BoxFit.cover,
                  alignment:Alignment.center,semanticLabel:'AniRepro cow on a farm')),
                // Match the subdued transparent-cow treatment from the web app.
                const Positioned.fill(child:DecoratedBox(decoration:BoxDecoration(
                  gradient:LinearGradient(begin:Alignment.centerLeft,end:Alignment.centerRight,
                    colors:[Color(0xea0d2b45),Color(0xcf16456b),Color(0xb5143551)])))),
                TweenAnimationBuilder<double>(duration:reduceMotion?Duration.zero:const Duration(milliseconds:800),
                  tween:Tween(begin:.88,end:1),builder:(context,value,child)=>Transform.scale(scale:value,child:child),
                  child:Container(padding:const EdgeInsets.all(16),height:128,width:128,
                    decoration:BoxDecoration(color:Colors.white,borderRadius:BorderRadius.circular(32)),
                    child:Image.asset('assets/logo.png',semanticLabel:'AniRepro 360 logo'))),
              ]))),
            const SizedBox(height:26),
            Text('Better records. Better herd decisions.',style:Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight:FontWeight.w800)),
            const SizedBox(height:10),
            Text('Manage animal health, reproductive history and farm activities in one secure workspace.',
              style:Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height:24),
            _Benefit(icon:Icons.pets_outlined,title:'Know every animal',description:'View farm profiles, health and breeding histories.'),
            _Benefit(icon:Icons.timeline,title:'Track reproductive care',description:'Record observations, pregnancies and delivery outcomes.'),
            _Benefit(icon:Icons.cloud_sync_outlined,title:'Work when connectivity is limited',description:'Access prepared records and synchronize supported changes after reconnecting.'),
            const SizedBox(height:24),
            FilledButton.icon(onPressed:()=>onGetStarted(),icon:const Icon(Icons.arrow_forward),label:const Text('Get started')),
            const SizedBox(height:8),
            Center(child:Text('Your account and farm permissions are verified by the AniRepro server.',
              textAlign:TextAlign.center,style:Theme.of(context).textTheme.bodySmall)),
          ])))))));
  }
}
class _Benefit extends StatelessWidget {
  const _Benefit({required this.icon,required this.title,required this.description});
  final IconData icon;final String title,description;
  @override Widget build(BuildContext context)=>Padding(padding:const EdgeInsets.only(bottom:15),child:Row(children:[
    CircleAvatar(backgroundColor:mint,foregroundColor:green,child:Icon(icon)),const SizedBox(width:14),
    Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      Text(title,style:Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight:FontWeight.w700)),
      Text(description,style:Theme.of(context).textTheme.bodySmall),
    ])),
  ]));
}
