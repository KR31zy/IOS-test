import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/api.dart';
void main(){
  test('HTTPS origin accepted; credentials, fragments, paths rejected',(){
    expect(Api.validateServer('https://farm.example.org/'),'https://farm.example.org');
    for(final value in ['https://user:pass@farm.example.org','https://farm.example.org/api','https://farm.example.org?q=1','https://farm.example.org/#link','file:///tmp/test','http://farm.example.org']) {
      expect(()=>Api.validateServer(value,allowHttp:false),throwsA(isA<ApiError>()));
    }
    expect(Api.validateServer('http://192.168.1.2:8000',allowHttp:true),'http://192.168.1.2:8000');
  });
}
