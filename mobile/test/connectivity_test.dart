import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:anirepro360_mobile/core/api.dart';

void main(){
  test('No implicit emulator origin on a fresh build',(){
    final api=Api();addTearDown(api.dispose);
    if(Api.configured.isEmpty){expect(api.needsServer,isTrue);expect(api.base,isEmpty);}
  });
  test('Health probe is read-only and never sends credentials or follows redirects',()async{
    final api=Api(client:MockClient((request)async{
      expect(request.url.toString(),'https://farm.example.org/api/health');
      expect(request.method,'GET');expect(request.followRedirects,isFalse);
      expect(request.headers.keys.map((k)=>k.toLowerCase()),isNot(contains('cookie')));
      return http.Response(jsonEncode({'status':'ok','service':'anirepro-api'}),200);
    }));addTearDown(api.dispose);
    await api.checkServer('https://farm.example.org');
  });
  for(final result in [http.Response('redirect',302),http.Response('unavailable',503),http.Response('<html/>',200),http.Response('{"status":"ok","service":"other"}',200)]){
    test('Health probe rejects invalid service ${result.statusCode} ${result.body}',()async{
      final api=Api(client:MockClient((_)async=>result));addTearDown(api.dispose);
      await expectLater(api.checkServer('https://farm.example.org'),throwsA(isA<ApiError>()));
    });
  }
  test('Network exceptions are actionable',()async{
    final api=Api(client:MockClient((_)async{throw http.ClientException('offline');}));addTearDown(api.dispose);
    await expectLater(api.checkServer('https://farm.example.org'),throwsA(isA<ConnectionError>()));
  });
}
