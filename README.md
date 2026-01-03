# Naver News Bot

간단한 스크립트로 네이버 뉴스 API를 호출해 특정 키워드의 최신 뉴스를 가져오고, 키워드 기반 간단 분석 태그를 붙여 콘솔 또는 텔레그램으로 전달합니다. 기본 쿼리는 테슬라이며, 최근 2일 이내 기사만 처리하고 중복을 캐시로 건너뜁니다.

## 주요 구성
- `naver_news_api/`: 네이버 뉴스 검색 REST API 클라이언트.
- `naver_news_bot.py`: 뉴스 검색, 캐싱, 키워드 분석, 텔레그램 발송을 포함한 엔트리포인트.

## 준비 사항
1. Python 3.9 이상
2. 패키지 설치
   ```bash
   pip install -r requirements.txt
   # requirements.txt가 없다면:
   pip install requests
   ```
3. 환경 변수 설정 (필수)

   다음 환경 변수를 OS 또는 실행 환경에 직접 등록해야 합니다.

   - `NAVER_CLIENT_ID`
   - `NAVER_CLIENT_SECRET`
   - `TELEGRAM_BOT_TOKEN` (선택)
   - `TELEGRAM_CHAT_ID` (선택)

   텔레그램 관련 값이 없으면 콘솔 출력만 수행합니다.

## 실행 방법
```bash
python naver_news_bot.py
```
동작 흐름:
1. 환경 변수를 읽어 네이버 뉴스 검색 API를 호출 (기본 쿼리: 테슬라, 20건, 최신순).
2. RFC 2822 날짜 파싱 후 최근 2일 기사만 유지.
3. `.news_seen.json` 캐시를 이용해 중복 뉴스 스킵(7일 보존).
4. 제목 키워드를 분석해 거시/실적/AI/EV 등 태그를 생성하고 요약 출력.
5. 텔레그램 토큰·채팅 ID가 있으면 메시지를 전송하고, 실패 시 콘솔에 원인을 알립니다.

## 커스터마이징 팁
- `naver_news_bot.py` 내부 `query`, `days`, `display`, `ANALYSIS_RULES` 값을 직접 수정해 검색어나 분류 규칙을 변경할 수 있습니다.
- `USE_NEWS_CACHE=False` 로 바꾸면 중복 캐시를 사용하지 않습니다.
- 메시지 길이 제한은 `TELEGRAM_MAX_MESSAGE_LENGTH` 로 조정할 수 있습니다.

## 문제 해결
- 네이버 자격 증명이 없거나 잘못되면 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` 미설정 오류가 발생합니다.
- 텔레그램 전송 실패 시 API 응답 설명이 콘솔에 출력되며, 이후 실행 중 텔레그램 전송을 중단합니다.
- 캐시 파일이 손상되면 자동으로 무시하고 새로 기록합니다.
