import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/api.dart';
import 'package:anirepro360_mobile/core/theme.dart';
import 'package:anirepro360_mobile/screens/workspace.dart';

class _FarmApi extends Api {
  _FarmApi() {
    user={'id':'cow-hero-test','name':'Farmer','email':'example@example.invalid'};
  }
  @override Future<dynamic> get(String path) async {
    if (path == '/api/farms') {
      return [
      {'id':'farm-1','name':'My Cattle Farm','role':'farm_manager',
       'permissions':['dashboard.view','animals.view']}
      ];
    }
    if(path.endsWith('/summary')) return {'animals':1};
    return <dynamic>[];
  }
}

void main(){
  testWidgets('Home reuses the exact cow hero and the original app logo',(tester)async{
    final api=_FarmApi();addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(theme:appTheme(),home:Workspace(api:api)));
    await tester.pumpAndSettle();
    final picture=find.byKey(const Key('anirepro-cow-home'));
    expect(picture,findsOneWidget);
    final image=tester.widget<Image>(picture);
    expect((image.image as AssetImage).assetName,'assets/herd-hero.jpg');
    expect(image.fit,BoxFit.cover);
    expect(find.text('YOUR FARM WORKSPACE'),findsOneWidget);
    expect(find.text('My Cattle Farm'),findsWidgets);
    expect(find.byWidgetPredicate((w)=>w is Image&&w.image is AssetImage&&
      (w.image as AssetImage).assetName=='assets/logo.png'),findsWidgets);
  });
}
