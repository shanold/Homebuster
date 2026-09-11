# Homebuster Android release signing

Homebuster release APKs should all be signed with the **same private keystore**. Android uses that signing certificate to decide whether a new APK is a legitimate upgrade of the installed Homebuster app.

## One-time setup

Choose a safe location **outside the Homebuster source folder** for the key, for example:

```text
/home/yourname/AndroidKeys/Homebuster-release.jks
```

Create the key with the Java `keytool` command:

```bash
mkdir -p ~/AndroidKeys
keytool -genkeypair \
  -v \
  -keystore ~/AndroidKeys/Homebuster-release.jks \
  -alias homebuster \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000
```

`keytool` will ask for a keystore password and certificate details. Use a strong password that you can preserve. For a private self-hosted app, the name/organization fields are simply certificate labels; they do not need to be a company registration.

**DO NOT lose this keystore or its passwords.** Future Homebuster APKs must use the same keystore if Android is to install them as upgrades over the existing release app.

## Configure this Homebuster checkout

From the `android` directory:

```bash
cp keystore.properties.example keystore.properties
```

Edit `keystore.properties`:

```properties
storeFile=/home/yourname/AndroidKeys/Homebuster-release.jks
storePassword=YOUR_KEYSTORE_PASSWORD
keyAlias=homebuster
keyPassword=YOUR_KEY_PASSWORD
```

`keystore.properties` is intentionally ignored by Git. Never upload it with your source, and never put the keystore itself inside the Homebuster project.

## Build a signed release APK

Linux/macOS:

```bash
cd android
./gradlew assembleRelease
```

Windows PowerShell:

```powershell
cd android
.\gradlew.bat assembleRelease
```

The resulting APK will normally be:

```text
android/app/build/outputs/apk/release/app-release.apk
```

If the signing configuration is missing, Homebuster intentionally stops the release build with a message pointing back to this guide. Debug builds still work normally.

## Verify the APK signature

If the Android SDK build-tools are on your PATH:

```bash
apksigner verify --verbose --print-certs app/build/outputs/apk/release/app-release.apk
```

You should see that APK Signature Scheme v2/v3 verification succeeds and a signer certificate is present.

You can also record the certificate fingerprint:

```bash
keytool -list -v -keystore ~/AndroidKeys/Homebuster-release.jks -alias homebuster
```

Keep the SHA-256 certificate fingerprint with your recovery notes.

## First release install

A debug APK and a release APK with the same package name are normally signed by **different certificates**. Android will not treat one as an upgrade of the other.

If Homebuster is currently installed from Android Studio/debug builds, you may need to:

1. Make sure anything important is already stored on the Homebuster server.
2. Uninstall the debug Homebuster app from the phone.
3. Install the new signed `app-release.apk`.
4. Log back into your Homebuster server and grant camera/local-network permissions again.

After that first switch, future release APKs signed with this same keystore should install directly over the previous release.

## Back up the signing identity

Keep at least two secure backups of:

- `Homebuster-release.jks`
- the keystore password
- the key password
- the alias (`homebuster`)
- the SHA-256 certificate fingerprint

A password manager plus an encrypted/offline backup is reasonable.

The private key is effectively the long-term identity of your Homebuster Android app. **Every future release must use the same keystore.**
