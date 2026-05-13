# 작은 정령들 — 휴식 동반자 위젯

화면 한구석에 조용히 떠 있는 안티-열품타 데스크탑 위젯.
정령을 클릭하면 휴식 카드 한 장을 건네받고, 마치면 정령이 자란다.

## 개발

```bash
npm install
npm run dev          # Vite + Electron 동시 실행
```

빌드 (Windows .exe):

```bash
npm run build:win
```

## 구조

```
src/main/         Electron 메인 (창 설정, IPC, 파일 입출력)
src/renderer/     Vite 렌더러 (UI, 모듈)
  modules/        도메인 로직 (정령 상태, 미션, 성장, 시들기 등)
  components/     화면 컴포넌트
  styles/         수채화 톤 CSS
data/             pets.json, missions.json
assets/pets/      정령별 4단계 SVG (시즌 1: 10종 × 4장)
```

## 핵심 루프

1. 정령을 클릭 → 카드 한 장 등장 (시간대/최근 사용 필터)
2. 수행 → 정령이 살짝 기뻐하고 휴식 포인트 +1
3. 60분 쿨다운, 그 사이엔 졸고 있음
4. 50포인트 누적 시 정령이 컬렉션 책장에 자리잡고 새 정령 등장
5. 시즌 1 컬렉션이 모두 차면 시즌 2의 새 결이 펼쳐짐

## 데이터 위치

런타임 상태와 사진은 `app.getPath('userData')` 아래에 저장된다.
- `state.json`: 정령 상태, 누적치, 설정
- `photos/`: 미션에서 모은 원본 사진
