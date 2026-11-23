import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/api.dart';
import 'package:anirepro360_mobile/screens/records.dart';
void main(){
  test('Role permissions do not grant unauthorized clinical writes',(){
    final f=<String,dynamic>{'permissions':['health.observe','animals.view']};
    expect(canRecord(f,'health'),true);expect(canRecord(f,'pregnancy'),false);expect(allowed(f,'reports.export'),false);
  });
  test('Server category names and path are preserved',(){
    expect(kinds['reproduction'],contains('estrus'));
    expect(animalPath({'id':'farm1'},{'id':'animal1'}),'/api/farms/farm1/animals/animal1');
  });
  test('Mutation keys contain 192 random bits encoded as hex',(){
    final k=nonce();expect(k, matches(RegExp(r'^[a-f0-9]{48}$')));expect(nonce(),isNot(k));
  });
}
