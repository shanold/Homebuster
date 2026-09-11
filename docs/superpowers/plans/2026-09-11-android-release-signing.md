# Android Release Signing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Homebuster Android builds a stable release signing identity without committing the private key or passwords.

**Architecture:** Keep the release keystore outside the source tree. Store only the local path/alias/passwords in an ignored `android/keystore.properties` file. Gradle loads that file for release builds, refuses to create a release APK when signing configuration is missing, and leaves debug builds unchanged.

**Tech Stack:** Android Gradle Plugin 9.4.0, Kotlin DSL, Java `keytool`, Android APK signing.

**Spec:** Conversation approval on 2026-09-11 to add proper signed release APK support after a Play Protect block.

## Global Constraints

- Do not commit or package a private `.jks`/`.keystore` file.
- Do not commit `keystore.properties` or signing passwords.
- Existing debug build workflow must continue to work.
- Existing application ID remains `com.homebuster.mobile`.
- Release signing certificate must remain the same for future Homebuster APK upgrades.

---

### Task 1: Add release-signing Gradle configuration
- [ ] Write a source-contract test requiring ignored local signing config and release signing support.
- [ ] Run it and confirm it fails on v0.3.14.
- [ ] Load `android/keystore.properties` in `app/build.gradle.kts`.
- [ ] Configure a named `release` signing config and attach it to the release build type.
- [ ] Fail release tasks with a readable message if the signing file/fields are missing.
- [ ] Re-run the contract test.

### Task 2: Add safe local configuration and instructions
- [ ] Add `android/.gitignore` entries for `keystore.properties`, keystores, build output, and local Android SDK settings.
- [ ] Add `android/keystore.properties.example` containing placeholders only.
- [ ] Add `android/RELEASE_SIGNING.md` with one-time `keytool` creation, property setup, release build, certificate verification, backup, and upgrade guidance.
- [ ] Update the project README Android section to point to the signed release workflow.

### Task 3: Version and verification
- [ ] Bump the Android app version to v0.3.15; server code remains v0.3.14 because no server behavior changes.
- [ ] Run Python/source-contract checks.
- [ ] Verify no keystore/password/private key is present in the ZIP.
- [ ] Verify Docker port remains `8092:8000`.
- [ ] Package `Homebuster-v0.3.15-web-plus-android.zip`.
