# Tablet Spoof Patcher

스플릿 APK 번들(`.apkm`)을 [LSPatch](https://github.com/JingMatrix/LSPatch) + [TabletSpoof](https://github.com/miner7222/TabletSpoof)로 패치해서,
앱이 기기를 **Galaxy Tab S10 Ultra**로 인식하게 만들고 USB로 연결된 기기에 자동 설치까지 해주는 Windows GUI 도구입니다.

## 사용법

1. [Releases](../../releases)에서 `TabletSpoofPatcher.exe`를 받습니다. (Python 설치 불필요)
2. 패치할 앱의 `.apkm` 파일을 준비합니다. (예: APKMirror 번들)
3. 기기에서 **개발자 옵션 > USB 디버깅**을 켜고 PC에 USB로 연결합니다. (기기 화면의 허용 창을 누르세요)
4. exe를 실행하고 `.apkm`을 선택(또는 드롭) 후 **패치 시작**을 누릅니다.

자동 설치를 끄면 `output\` 폴더에 패치된 APK들과 `.apks` 번들(SAI 등으로 설치)이 만들어집니다.

## 동작 방식

- `.apkm`을 풀어 base/split APK 전체를 LSPatch(`-l 2`)로 패치하고 TabletSpoof 모듈을 내장합니다.
- 필요한 도구는 **이 프로젝트에 포함되어 있지 않고**, 첫 실행 때 공식 배포처에서 exe 옆 `tools\` 폴더로 내려받습니다.

| 도구 | 출처 |
|---|---|
| Java 21 | [Eclipse Temurin (Adoptium)](https://adoptium.net/) |
| LSPatch | [JingMatrix/LSPatch](https://github.com/JingMatrix/LSPatch) |
| TabletSpoof | [miner7222/TabletSpoof](https://github.com/miner7222/TabletSpoof) |
| adb | [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (PC에 adb가 있으면 그걸 사용) |

## 직접 빌드

```
pip install pyinstaller tkinterdnd2
pyinstaller --onefile --windowed --collect-all tkinterdnd2 --name TabletSpoofPatcher tablet_spoof_patcher.py
```

`v*` 태그를 푸시하면 GitHub Actions가 exe를 빌드해 Release에 올립니다.

## 주의

- 패치된 앱은 서명이 달라, **기존 앱을 삭제하고 설치**해야 합니다. 앱 데이터가 삭제되니 백업하세요.
- 앱의 기기 정보를 바꾸는 것은 해당 앱 제공사의 이용약관에 어긋날 수 있고, 계정 제재 위험이 있습니다. **사용에 따른 책임은 사용자에게 있습니다.**
- 이 프로젝트는 어떤 앱 제공사와도 무관하며, 앱 APK나 패치된 결과물을 **배포하지 않습니다.** 각자 받은 파일을 직접 패치하세요.
- 서명 없는 exe라서 Windows SmartScreen/백신이 경고할 수 있습니다. 불안하면 소스를 확인하고 직접 빌드하세요.

## 라이선스

MIT (이 저장소의 코드). 내려받아 사용하는 외부 도구는 각자의 라이선스를 따릅니다. LSPatch는 GPLv3입니다.
