# Standalone Android APK Build Guide

This guide explains how to generate a **standalone Android `.apk` installer** for the **Housing Society VTS** mobile app so that security guards, residents, and committee members can install and run the app directly on their phones **without Expo Go**.

---

## 🏗️ Architecture

```
+------------------------------------+
|  React Native App (HousingSociety) |
+------------------+-----------------+
                   |
     npx eas build -p android --profile preview
                   |
                   v
+------------------------------------+
|   EAS Cloud Builder (Free Expo)    |
|   - Bundles JS & Assets            |
|   - Compiles Native Android code   |
|   - Packages into APK              |
+------------------+-----------------+
                   |
                   v
+------------------------------------+
|      HousingSociety.apk File       |
|  Directly installable on phones    |
+------------------------------------+
```

---

## 📋 Steps to Build the Standalone APK

### 1. Create a Free Expo Account (If you don't have one)
Sign up for a free account at [https://expo.dev/signup](https://expo.dev/signup).

### 2. Log in to EAS CLI
In PowerShell inside the mobile app folder:
```powershell
cd C:\Users\gauri\Projects\HousingSocietyApp
npx eas login
```
Enter your Expo email/username and password.

### 3. Trigger the APK Build
Run the build command using the configured `preview` profile:
```powershell
npx eas build -p android --profile preview
```

### 4. What Happens During the Build:
1. EAS will ask: *"Generate a new Android Keystore?"* → Press **Enter** (Yes). EAS manages your signing key securely in the cloud.
2. The code is uploaded to Expo's cloud build servers.
3. EAS compiles the app and produces an installable `.apk` file.
4. When finished (typically ~5-10 minutes), the terminal will print a **direct download link** and a **QR code**.
5. Scan the QR code or open the link on your Android phone to download and install `HousingSociety.apk`!

---

## 📱 Sideloading / Installing on Android Phones
1. Download the `.apk` file on the Android device.
2. Tap the file to install.
3. If prompted: *"For your security, your phone is not allowed to install unknown apps from this source"*, tap **Settings** and toggle **Allow from this source**.
4. Tap **Install**. The app will appear on the phone's home screen with its own icon and title: **Housing Society VTS**.

---

## 🌐 Connecting Standalone App to Production Server
1. When you deploy the Django backend to your society's cloud server or gatehouse server (e.g. `https://api.societyvts.com`), open the app.
2. On the login screen, tap **⚙️ Server: ...**.
3. Enter your production API URL (e.g. `https://api.societyvts.com/api/v1`) and tap **Save URL**.
4. The app will permanently remember this server endpoint.
