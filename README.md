**ChordBoard (Windows 11 · 5-Key Chording Keyboard)**



Windows 11에서 \*\*5개의 키\*\*만으로 영/한 문자 입력과 단축키를 ‘합주(Chording)’로 처리하는 입력 도구.

\# Tap strap 시리즈에서 따왔습니다. (키 목록은 chordboard_keymap_filled.xlsx에 있음)



**✨ 주요 특징**



* **멀티탭 카운트:** 같은 비트패턴을 빠르게 1/2/3번 탭 → 각각 `cnt=1/2/3` 매핑.
* **모드 레이어: `**기본 / SHIFT / SWITCH / Fn / ctrl (Fn은 오버레이로 우선 조회, 없으면 기본으로 폴백).
* **양손(Hand) 전환:** `RIGHT/LEFT` 두 레이아웃 지원. 5키 바인딩을 학습 모드로 즉시 재설정.
* **키 억제(suppress):** 합주 ON일 때만 5키 원래 입력을 차단하여 이중 입력 방지.
* **매핑 명령(Command**): 매핑값에서 `cmd:toggle\_active`, `cmd:set\_mode=...`, `cmd:exit` 등 내부 동작 호출.
* **3-창 UI:**



* &nbsp; 창 1 Control: 모드·언어·손·토글·활성화
* &nbsp; 창 2 Current Bits: LED 스타일 비주얼, 마지막 출력 로그
* &nbsp;  창 3 Bindings \& Layouts: 5키 학습, 현재 레이아웃, 내장 단축키



---



**📁 구성**





**chordboard\_ui\_multiwin.py**   # 3-창 UI

**chordboard\_win11.py**         # 백엔드(후크/멀티탭/전송/명령/손모드)

**mapping\_clean.json**          # (lang, mode, count, bits) → value 맵

**ChordBoard.ico**              # 아이콘





> 단일 실행파일(exe)로 배포해도 동작하도록 경로 처리가 되어 있음(`sys.\_MEIPASS` 지원).



---



**🚀 빠른 시작**



&nbsp;**방법 A) 파이썬 스크립트로 실행**



1\. Python 3.x 설치 후 패키지:



&nbsp;    **powershell**

&nbsp;  py -3 -m pip install keyboard

&nbsp;   

2\. 위 3개 파일(UI/백엔드/매핑)을 **한 폴더**에 둔다.

3\. \*\*관리자 PowerShell\*\*에서 실행:



&nbsp;    **powershell**

&nbsp;  py -3 .\\chordboard\_ui\_multiwin.py

&nbsp;  

4\. UI 창 1에서 \*\*Toggle Active\*\*를 눌러 합주 ON.



**방법 B) 단일 EXE 실행**



* `chordboard\_ui\_multiwin.exe`를 관리자 권한으로 실행.
* &nbsp;exe에 매핑을 번들링하지 않았다면, 같은 폴더에 `mapping\_clean.json`을 함께 둔다.



&nbsp;(선택) PyInstaller 빌드



powershell

pyinstaller --onefile --windowed 

&nbsp; --icon ChordBoard.ico 

&nbsp; --add-data "mapping\_clean.json;." 

&nbsp; --hidden-import chordboard\_win11 

&nbsp; chordboard\_ui\_multiwin.py

```



* &nbsp;`--add-data` : 매핑 포함(Windows는 세미콜론 `;`, PowerShell은 위처럼 그대로 사용 가능)
* &nbsp;`--hidden-import` : 백엔드 모듈을 번들에 강제 포함



---



&nbsp;**🕹 사용법**



&nbsp;1) 손/언어/모드



* **합주 ON/OFF:** `Ctrl+Alt+M` 또는 UI 버튼
* **언어 전환**: `Ctrl+Alt+L` (EN↔KO)
* **손 전환**: `Ctrl+Alt+H` (LEFT↔RIGHT), 또는 `Ctrl+Alt+←/→`로 강제 지정
* **모드 선택**: UI의 `기본 / SHIFT / SWITCH / Fn  



2\) 멀티탭(카운트)



\* **같은 비트패턴을 \*\*한 번\*\* 탭 → `cnt=1`**

**\* 빠르게 \*\*두 번\*\* → `cnt=2`**

**\* \*\*세 번\*\* → `cnt=3`**

**\* 기본 값: `DEBOUNCE=0.02s`, `TAP\_GAP=0.25s` (백엔드 상단 상수)**



&nbsp;3) 5키 바인딩(학습 모드)



* 창 3 → **Start Learn** → 현재 손의 5키를 \*\*1번→5번\*\* 순서대로 누르면 적용(ESC 취소)



4\) 내장 단축키(프로그램 자체)



* **Ctrl+Alt+M** : 합주 ON/OFF
* **Ctrl+Alt+L** : EN↔KO
* **Ctrl+Alt+H**: 손 전환
* **Ctrl+Alt+←/→** : 손 강제 지정
* **Ctrl+Alt+Q** : 종료



---



\## 🧩 매핑 규칙 (`mapping\_clean.json`)



\* 구조: \*\*언어(lang) → 모드(mode) → 카운트("1|2|3") → 비트패턴(5자리 문자열)\*\* → \*\*값\*\*

\* 비트패턴: 현재 손에서 정의된 \*\*b1..b5\*\* 순서 기준. 예) `"01100"`

\* 값 종류:



&nbsp; 1. \*\*한 글자\*\* (예: `"a"`, `"ㄱ"`) → `keyboard.write()`로 출력

&nbsp; 2. \*\*키 이름/조합\*\* (예: `"enter"`, `"left"`, `"ctrl+v"`, `"windows+tab"`)

&nbsp; 3. \*\*명령(Command)\*\*: `"cmd:..."` 형식 → 내부 동작 실행



&nbsp;  **예시**



&nbsp; json

{

&nbsp; "EN": {

&nbsp;   "기본": {

&nbsp;     "1": {

&nbsp;       "01100": "t",

&nbsp;       "11100": "cmd:set\_mode=SHIFT",

&nbsp;       "00111": "cmd:set\_mode=SWITCH",

&nbsp;       "11111": "space"

&nbsp;     },

&nbsp;     "2": {

&nbsp;       "11000": "print screen",

&nbsp;       "11010": "ctrl+v",

&nbsp;       "10011": "shift+enter"

&nbsp;     },

&nbsp;     "3": {

&nbsp;       "00100": "windows+r",

&nbsp;       "00010": "cmd:exit",

&nbsp;       "11010": "ctrl+a"

&nbsp;     }

&nbsp;   }

&nbsp; }

}





&nbsp; **지원 명령(일부)**



* &nbsp;`cmd:toggle\_active`, `cmd:set\_active=on/off`
* &nbsp;`cmd:toggle\_lang`, `cmd:set\_lang=EN/KO`
* &nbsp;`cmd:toggle\_hand`, `cmd:set\_hand=LEFT/RIGHT`
* &nbsp;`cmd:set\_mode=기본/SHIFT/SWITCH/Fn`
* &nbsp;`cmd:toggle\_ctrl`, `cmd:toggle\_fn`
* &nbsp;`cmd:exit`



> 키워드 정규화: `window+\*` → `windows+\*`, `window+tap` → `windows+tab`, 방향키 명칭 `Arrow Left/Right/Up/Down` → `left/right/up/down`.



---



🧯 트러블슈팅



* **원래 키가 같이 찍힘: 합주가 ON인지, 관리자 권한 실행인지 확인. ON일 때만 5키 suppress.**
* **MISS 로그가 뜸: `(lang, mode, count, bits)` 조합이 매핑에 없음.**
* **같은 비트가 다른 count에 있다면 멀티탭 수를 맞추거나 매핑의 count 라벨을 고친다.**
* **연타 인식이 둔함/예민함: `TAP\_GAP`(연속 탭 허용 간격)과 `DEBOUNCE`를 조정.**
* **UI LED 안 바뀜: 합주 OFF면 5키가 억제되지 않음. ON으로 전환 후 확인.**
* **exe에서 파일을 못 찾음: 빌드시 `--hidden-import chordboard\_win11` + `--add-data "mapping\_clean.json;."` 사용.**



---



**🔧 커스터마이즈**



* &nbsp;손별 5키: 코드 상단의 `RIGHT\_CHORD\_KEYS / LEFT\_CHORD\_KEYS` 또는 UI \*\*Learn Mode\*\*로 변경.
* &nbsp;아이콘 교체: `ChordBoard.ico`를 바로가기/빌드에 지정.
* &nbsp;로깅/사운드/프로필 전환 등은 추후 플러그인 형태로 확장 가능.

---



**🤝 기여하기**



&nbsp; **버그/개선 제안은 이슈로 남기고, PR 시에는**



* 재현 로그(콘솔 출력)
* 매핑 일부(문제난 조합)
* OS/권한/파이썬 버전

&nbsp;   을 포함해 주세요.



---



&nbsp;**📜 라이선스**



&nbsp;MIT 라이선스



