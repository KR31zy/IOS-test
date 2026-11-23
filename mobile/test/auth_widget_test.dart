import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/api.dart';
import 'package:anirepro360_mobile/core/theme.dart';
import 'package:anirepro360_mobile/screens/auth.dart';
void main(){
 testWidgets('Login has credential fields and recovery navigation', (tester) async {
   final api=Api();addTearDown(api.dispose);
   await tester.pumpWidget(MaterialApp(theme:appTheme(),home:AuthScreen(api:api)));
   expect(find.text('Welcome Back'),findsOneWidget);
   expect(find.text('Password'),findsOneWidget);
   await tester.ensureVisible(find.text('Google'));
   expect(find.text('Google'),findsOneWidget);
   expect(find.text('Apple'),findsOneWidget);
   await tester.ensureVisible(find.text('Forgot password?'));
   await tester.tap(find.text('Forgot password?'));await tester.pumpAndSettle();
   expect(find.text('Send recovery link'),findsOneWidget);
 });
}
