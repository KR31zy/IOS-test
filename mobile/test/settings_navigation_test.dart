import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/api.dart';
import 'package:anirepro360_mobile/core/theme.dart';
import 'package:anirepro360_mobile/screens/workspace.dart';

class _LocalApi extends Api {
  _LocalApi() {user={'id':'test-user','name':'Test Farmer','email':'test@example.invalid'};}
  @override Future<dynamic> get(String path)async{
    if (path == '/api/farms') {
      return [
      {'id':'farm-test','name':'Farm Test','role':'farm_manager','permissions':['dashboard.view']}
      ];
    }
    if(path.endsWith('/summary'))return {'animals':0};
    if(path=='/api/me')return {'name':'Test Farmer','email':'test@example.invalid','farms':[]};
    return [];
  }
}

void main(){
  testWidgets('Back from More returns Home instead of exiting',(tester)async{
    final api=_LocalApi();addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(theme:appTheme(),home:Workspace(api:api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('More').last);
    await tester.pumpAndSettle();
    expect(find.text('Clinical workspace'),findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('Welcome, Test Farmer'),findsOneWidget);
  });
  testWidgets('Back from Profile & settings returns Home',(tester)async{
    final api=_LocalApi();addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(theme:appTheme(),home:Workspace(api:api)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('More').last);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Profile & settings'),200,scrollable:find.byType(Scrollable).first);
    await tester.tap(find.text('Profile & settings'));
    await tester.pumpAndSettle();
    expect(find.text('My profile'),findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('Welcome, Test Farmer'),findsOneWidget);
  });
}
