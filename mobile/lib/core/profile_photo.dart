import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

/// Device-local account photo. Farm/backend profile photo synchronization is
/// deliberately not claimed until an authenticated server avatar API exists.
class ProfilePhotoStore {
  static const maxBytes = 2 * 1024 * 1024;
  static const _storage = FlutterSecureStorage();
  static final _cipher = AesGcm.with256bits();

  static bool supportedImage(Uint8List bytes) {
    final png = bytes.length >= 8 && bytes[0] == 0x89 && bytes[1] == 0x50 &&
        bytes[2] == 0x4e && bytes[3] == 0x47 && bytes[4] == 0x0d &&
        bytes[5] == 0x0a && bytes[6] == 0x1a && bytes[7] == 0x0a;
    final jpg = bytes.length >= 3 && bytes[0] == 0xff && bytes[1] == 0xd8 && bytes[2] == 0xff;
    return bytes.isNotEmpty && bytes.length <= maxBytes && (png || jpg);
  }

  static Future<String> _scope(String origin, String accountId) async {
    final hash = await Sha256().hash(utf8.encode(jsonEncode([origin, accountId])));
    return hash.bytes.map((n) => n.toRadixString(16).padLeft(2, '0')).join();
  }

  static Future<(File, SecretKey)> _open(String origin, String accountId, {bool create = false}) async {
    final scope = await _scope(origin, accountId);
    final folder = Directory('${(await getApplicationSupportDirectory()).path}/profile-photos');
    if (create) await folder.create(recursive: true);
    final file = File('${folder.path}/$scope.enc');
    final keyName = 'anirepro-avatar-key:$scope';
    var encoded = await _storage.read(key: keyName);
    if (encoded == null) {
      if (!create || await file.exists()) throw StateError('Profile photo key unavailable.');
      encoded = base64Encode(await (await _cipher.newSecretKey()).extractBytes());
      await _storage.write(key:keyName, value:encoded);
    }
    return (file, SecretKey(base64Decode(encoded)));
  }

  static Future<Uint8List?> load(String origin, String accountId) async {
    final scope = await _scope(origin, accountId);
    final dir = await getApplicationSupportDirectory();
    final file = File('${dir.path}/profile-photos/$scope.enc');
    if (!await file.exists()) return null;
    final (_, key) = await _open(origin, accountId);
    final bytes = await file.readAsBytes();
    if (bytes.length < 28 || bytes.length > maxBytes + 28) throw const FormatException('Invalid profile image size');
    final box = SecretBox(bytes.sublist(12,bytes.length-16),nonce:bytes.sublist(0,12),mac:Mac(bytes.sublist(bytes.length-16)));
    final decoded = Uint8List.fromList(await _cipher.decrypt(box, secretKey:key));
    if (!supportedImage(decoded)) throw const FormatException('Invalid stored profile image');
    return decoded;
  }

  static Future<void> save(String origin, String accountId, Uint8List bytes) async {
    if (!supportedImage(bytes)) throw ArgumentError('Select a PNG or JPEG image smaller than 2 MB.');
    final (file, key) = await _open(origin, accountId,create:true);
    final box = await _cipher.encrypt(bytes,secretKey:key);
    final tmp = File('${file.path}.tmp');
    await tmp.writeAsBytes([...box.nonce, ...box.cipherText, ...box.mac.bytes],flush:true);
    await tmp.rename(file.path);
  }

  static Future<void> remove(String origin,String accountId) async {
    final scope = await _scope(origin, accountId);
    final dir = await getApplicationSupportDirectory();
    final file = File('${dir.path}/profile-photos/$scope.enc');
    if (await file.exists()) await file.delete();
    await _storage.delete(key:'anirepro-avatar-key:$scope');
  }
}
