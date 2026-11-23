import 'dart:io';
import 'dart:convert';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/features/offline/store.dart';

void main(){
  late Directory dir;
  late File file;
  late SecretKey key;
  PendingWrite write(String id,{String path='/api/farms/f1/animals',String name='Private farm record'})=>PendingWrite(
    key:id,path:path,body:{'name':name,'tag':'A-100'},createdAt:'2026-11-19T00:00:00Z');
  setUp(()async{dir=await Directory.systemTemp.createTemp('offline_test');file=File('${dir.path}/account.enc');key=await AesGcm.with256bits().newSecretKey();});
  tearDown(()async{await dir.delete(recursive:true);});
  test('Only idempotent animal and event creation paths are queueable',(){
    expect(queueable('/api/farms/f1/animals'),isTrue);
    expect(queueable('/api/farms/f1/animals/a1/events'),isTrue);
    expect(queueable('/api/farms/f1/animals/a1/attachments'),isFalse);
    expect(queueable('/api/auth/login'),isFalse);
    expect(queueable('/api/farms/f1/animals/a1/events?x=1'),isFalse);
    expect(cacheable('/api/auth/session'),isFalse);
    expect(cacheable('/api/farms/f1/members'),isFalse);
  });
  test('Offline cache TTL rejects expired and future timestamps',(){
    final now=DateTime.utc(2026,11,19,12);
    expect(withinOfflineWindow('2026-11-19T08:00:00Z',now),isTrue);
    expect(withinOfflineWindow('2026-11-18T12:00:00Z',now),isFalse);
    expect(withinOfflineWindow('2026-11-20T12:00:00Z',now),isFalse);
  });
  test('Encrypted cache and pending queue survive reopening',()async{
    final store=await OfflineStore.openFile(file,key);
    await store.cache('/api/farms',[{'name':'Private farm record'}]);
    await store.enqueue(write('abc123456'));
    expect(utf8.decode(await file.readAsBytes(),allowMalformed:true),isNot(contains('Private farm record')));
    final restored=await OfflineStore.openFile(file,key);
    expect(restored.queue.single.key,'abc123456');
    expect(restored.snapshot('/api/farms')!['value'][0]['name'],'Private farm record');
  });
  test('Duplicate idempotency keys cannot alter payload or add duplicate queue rows',()async{
    final store=await OfflineStore.openFile(file,key);
    await store.enqueue(write('abc123456'));
    await store.enqueue(write('abc123456'));
    expect(store.queue.length,1);
    await expectLater(store.enqueue(write('abc123456',name:'Different animal')),throwsStateError);
    expect(store.queue.single.body['name'],'Private farm record');
  });
  test('Blocked conflicts survive restart and cache clearing does not discard queued records',()async{
    final store=await OfflineStore.openFile(file,key);
    final entry=write('abc123456');
    await store.enqueue(entry);
    await store.update(entry.state(attempts:1,issue:'409 conflict',blocked:true));
    await store.cache('/api/farms',[]);
    await store.clearCache();
    final restored=await OfflineStore.openFile(file,key);
    expect(restored.snapshot('/api/farms'),isNull);
    expect(restored.queue.single.blocked,isTrue);
    expect(restored.queue.single.key,entry.key);
    await restored.remove(entry.key);
    expect(restored.queue,isEmpty);
  });
  test('Wrong encryption key and tampered ciphertext fail closed',()async{
    final store=await OfflineStore.openFile(file,key);
    await store.enqueue(write('abc123456'));
    final wrong=await AesGcm.with256bits().newSecretKey();
    await expectLater(OfflineStore.openFile(file,wrong),throwsA(anything));
    final bytes=await file.readAsBytes();bytes[13]^=1;await file.writeAsBytes(bytes);
    await expectLater(OfflineStore.openFile(file,key),throwsA(anything));
  });
  test('Concurrent local writes are serialized without losing drafts',()async{
    final store=await OfflineStore.openFile(file,key);
    await Future.wait([store.enqueue(write('abc123456')),store.enqueue(write('abc123457'))]);
    final restored=await OfflineStore.openFile(file,key);
    expect(restored.queue.length,2);
  });
  test('Removing revoked farm snapshots preserves other farms and the queue',()async{
    final store=await OfflineStore.openFile(file,key);
    await store.cache('/api/farms/f1/animals',[]);
    await store.cache('/api/farms/f2/animals',[]);
    await store.enqueue(write('abc123456'));
    await store.retainFarms({'f2'});
    expect(store.snapshot('/api/farms/f1/animals'),isNull);
    expect(store.snapshot('/api/farms/f2/animals'),isNotNull);
    expect(store.queue.length,1);
  });
}
