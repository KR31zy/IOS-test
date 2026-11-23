import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/profile_photo.dart';

void main() {
  test('accepts valid PNG/JPEG signatures and rejects other binary data',(){
    expect(ProfilePhotoStore.supportedImage(Uint8List.fromList([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a])),isTrue);
    expect(ProfilePhotoStore.supportedImage(Uint8List.fromList([0xff,0xd8,0xff,0x00])),isTrue);
    expect(ProfilePhotoStore.supportedImage(Uint8List.fromList([0x25,0x50,0x44,0x46])),isFalse);
    expect(ProfilePhotoStore.supportedImage(Uint8List(2*1024*1024+1)),isFalse);
  });
}
