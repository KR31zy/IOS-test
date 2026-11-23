import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/screens/onboarding.dart';

void main() {
  testWidgets('first-use introduction has original logo and Get started action',(tester)async{
    var activated=false;
    await tester.pumpWidget(MaterialApp(home:OnboardingPage(onGetStarted:()async{activated=true;})));
    expect(find.text('WELCOME TO ANIREPRO 360'),findsOneWidget);
    expect(find.text('Get started'),findsOneWidget);
    expect(find.byWidgetPredicate((widget)=>widget is Image&&widget.image is AssetImage&&
      (widget.image as AssetImage).assetName=='assets/herd-hero.jpg'),findsOneWidget);
    expect(find.byWidgetPredicate((widget)=>widget is Image&&widget.image is AssetImage&&(widget.image as AssetImage).assetName=='assets/logo.png'),findsOneWidget);
    await tester.ensureVisible(find.text('Get started'));
    await tester.tap(find.text('Get started'));
    expect(activated,isTrue);
  });
}
