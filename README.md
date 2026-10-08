# 집단적독백 공연 아카이브

빌드 도구와 서버 의존성이 없는 HTML/CSS/JavaScript 사이트입니다. 홈, 연도별 아카이브, 레퍼토리, 멤버, 소개 페이지가 JSON 데이터를 함께 사용합니다. 캐릭터와 포스터는 기존 자료에서 가져왔습니다.

## 로컬 실행

Python 3.10 이상으로 공개 산출물을 만든 후 HTTP 서버로 엽니다. 별도 패키지 설치가 필요하지 않습니다.

```powershell
python scripts/build.py
python -m http.server 8000 --bind 127.0.0.1 --directory dist
```

브라우저에서 `http://127.0.0.1:8000/`를 엽니다. HTML 파일을 직접 더블클릭하면 브라우저의 로컬 JSON 읽기 제한 때문에 로딩되지 않습니다. 원본 자료를 제공하지 않도록 서버는 **dist만** 제공합니다.

```powershell
python scripts/validate.py
python scripts/validate.py dist
python scripts/data-check.py
node --check assets/js/site.js
```

`scripts/browser-check.py`는 Playwright가 이미 설치된 환경의 선택적인 브라우저 검증입니다. 실제 실행 결과는 `test-results/validation.md`에 남깁니다.

## 구조와 데이터 추가

- HTML 5개와 `assets/`: 공통 디자인, 안전한 DOM 렌더링, 검색·필터, 확대 모달.
- `data/site.json`: 밴드 소개, 공식 채널, 연도 설정, 공개용 근거 목록.
- `data/members.json`: 닉네임과 캐릭터. `roles`는 확인된 역할만 기재합니다.
- `data/songs.json`: 곡의 안정적인 ID, 정규화 제목, 원본 별칭, 확인된 작곡 정보.
- `data/concerts-연도.json`: 공연과 곡별 기록. 공연의 완료와 각 곡의 연주 확인은 별도입니다.
- `scripts/public-files.json`: 사람이 검토한 HTML·코드·이미지·매체의 명시적 허용 목록.
- `private-notes/`: 조사 기록과 확인 목록, 로컬 추출물. 배포 및 신규 커밋 제외.
- `dist/`: 허용 목록과 설정에 등록된 JSON만으로 만드는 공개 산출물. 이미지의 텍스트·EXIF 메타데이터를 제거합니다. 픽셀은 유지합니다.

새 연도는 `data/site.json`의 `years`에 설정과 `data/concerts-YYYY.json` 파일을 추가합니다. 같은 곡에는 기존 `songId`를 재사용하고, 각 공연과 곡 항목의 `id`는 고유하게 만듭니다. `sourceIds`는 공개용 근거 ID를 가리키며 사적인 원본 경로를 적지 않습니다. 이미지와 공개 자료를 추가하면 검토 후 허용 목록에도 등록하고, 커밋할 파일은 `.gitignore` 예외 목록에도 추가합니다. 원본 이미지·문서를 덮어쓰지 않습니다.

`status`: `completed` / `scheduled`. `evidenceStatus`: `confirmed`(연주 확인) / `program`(인쇄 프로그램) / `planned`(진행 계획). `datePrecision`: `day` / `month` / `unknown`. 일자를 모르면 월만, 전혀 모르면 `date: null`로 남깁니다. 번호가 확인되지 않은 공연은 `no: null`입니다. 낭송은 `kind: event` 또는 곡의 `additionalEvents`로 구분하며 곡 수에 중복 합산하지 않습니다.

공연 역할 연결은 명시적인 실명→닉네임 대응을 로컬에서 확인한 뒤 공개 데이터에는 `{ "memberId": "member-…", "role": "기타" }`만 넣습니다. `creditsStatus`로 전체 출연진 확인 여부를 표시합니다. 부분 확인한 출연진은 보여 주되 나머지는 확인 중으로 둡니다. 멤버의 `roles`를 추가할 때는 `rolesStatus: confirmed`와 근거를 함께 기록합니다. 과거 공연의 ‘전원’을 현재 7명으로 대체하지 않습니다.

매체 공개와 공연 카드 공개는 별도입니다. `visibility: private` 공연은 dist 데이터에서 제외됩니다. `mediaVisibility: withheld` 공연에는 공개 매체를 넣지 않습니다. 검토한 영상 URL만 곡별 `videoUrl`에 넣으며, 영상은 사용자가 버튼을 누른 후 로딩합니다. 사진은 `media`에 `type: image`, `reviewed: true`로 등록할 수 있습니다.

## GitHub Pages

현재 폴더는 Git 저장소가 아니며 계정·저장소명·원격 주소를 확인할 수 없었습니다. 저장소를 생성하거나 push하지 않았습니다. 연결할 저장소가 정해지면 공개 파일과 필요한 스크립트만 커밋하세요.

1. 저장소 **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
2. 기본 브랜치가 `main`과 다르면 `.github/workflows/pages.yml`의 브랜치를 변경합니다.
3. 사용자가 push하거나 Actions에서 워크플로를 수동 실행하면 공개 허용 목록 검증 후 **dist만** Pages 아티팩트에 올립니다.
4. 주소 형식은 `https://계정.github.io/저장소명/`이며, 사용자 사이트 저장소는 `https://계정.github.io/`입니다. JSON·이미지·페이지는 상대 경로를 사용합니다.

워크플로는 [GitHub 공식 정적 Pages 예제](https://github.com/actions/starter-workflows/blob/main/pages/static.yml)와 [Python 설정 액션의 공식 사용법](https://github.com/actions/setup-python)을 참고했습니다. 업로드 대상은 예제의 저장소 전체 대신 검증한 `dist`로 제한했습니다.

`.gitignore`는 **새 파일의 추적을 막을 뿐 이미 추적된 파일이나 Git 이력을 숨기지 않습니다.** 공개 저장소에서는 Pages에 제외한 원본도 저장소에서 읽힐 수 있습니다. 원본 2025/·2026/, 메일, 실명 매핑, 기획안과 추출 자료는 공개 저장소에 넣지 마세요. 기존 민감 파일이 이미 추적되어 있다면 별도 검토해야 하며, 이 프로젝트는 Git 이력 삭제나 강제 push를 수행하지 않습니다.

## 현재 확인 범위

2025 공연 3건과 프로그램에 기록된 13곡, 2026-10-18 15:00 고덕우 갤러리 예정 공연을 반영했습니다. 2026 인쇄본 10곡과 대본에 추가된 마지막 곡은 구분합니다. 가족음악회의 확인된 연주 3곡 외에는 자료 종류를 그대로 표시하며 프로그램만으로 실제 연주를 확정하지 않습니다.

실명과 닉네임 대응, 공연별 출연진, No.3 실제 순서·이벤트·앵콜, 현장 매체는 확인 중입니다. 2026 11월 수녀원 공연과 축가 2회는 확정 날짜와 공개 범위가 없어 등록하지 않았습니다. 자세한 로컬 조사 기록은 `private-notes/confirmation-checklist.md`를 참고하세요. PDF 텍스트를 추출하고 이미지 프로그램과 대조했으며, HWP는 미리보기만 추출했습니다.
