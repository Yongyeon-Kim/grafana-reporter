# Grafana 알림 리포터

Grafana, Prometheus, Loki 등에서 수집된 데이터를 기반으로 주기적인 요약 리포트를 생성하고 Mattermost/이메일로 전송하는 파이썬 기반 도구입니다.

## 주요 기능

- **데이터 소스 연동**: Grafana, Prometheus, Loki 데이터 소스에서 직접 데이터를 조회합니다.
- **자동 리포트 생성**: 지정된 Grafana 대시보드의 패널 쿼리를 실행하여 데이터를 요약하고 리포트를 생성합니다.
- **다양한 출력 형식**: 텍스트(Text) 및 테이블(Table) 형식의 리포트를 지원합니다.
- **Mattermost/이메일 통합**: 생성된 리포트를 Mattermost 웹훅 또는 SMTP 이메일로 자동 전송합니다.
- **API 상태 확인**: Gitea 워크플로우를 통해 주기적으로 API 상태를 확인하고 장애 발생 시 Mattermost로 알림을 전송합니다.
- **유연한 설정**: `.env` 파일을 통해 Grafana URL, API 키, 대시보드 UID 등의 설정을 쉽게 변경할 수 있습니다.

## 프로젝트 구조

```
.
├── .gitea/
│   └── workflows/
│       ├── main.yml           # 주기적으로 테이블 리포트를 생성하는 Gitea 워크플로우
│       └── health_check.yml   # API 상태를 주기적으로 확인하는 Gitea 워크플로우
├── src/
│   ├── clients/      # Grafana, Loki, Prometheus API 클라이언트
│   ├── services/     # 리포트 생성, 데이터 요약 등 핵심 비즈니스 로직
│   ├── setting/      # 환경 변수 및 설정 관리
│   ├── utils/        # 시간 처리 등 유틸리티 함수
│   ├── report_table.py # 테이블 형식 리포트 생성 스크립트
│   └── report_text.py  # 텍스트 형식 리포트 생성 스크립트
├── run_table.sh      # 테이블 리포트 실행 스크립트
├── run_text.sh       # 텍스트 리포트 실행 스크립트
├── requirements.txt  # 프로젝트 의존성
└── .env.example      # 환경 변수 설정 예시 파일
```

## 자동화 워크플로우

### 테이블 리포트 생성 (`.gitea/workflows/main.yml`)

- **목적**: 스케줄에 따라 자동으로 테이블 형식의 리포트를 생성하고 Mattermost/이메일로 전송합니다.
- **동작**:
    - 매일 15:00 UTC (`cron: '0 15 * * *'`)에 자동으로 실행됩니다.
    - 월요일에는 지난 7일간의 데이터를 요약(`run_table.sh 7d`), 그 외 요일에는 지난 24시간의 데이터를 요약(`run_table.sh 24h`)하여 리포트를 생성합니다.
    - 실행 로그는 `report-logs`라는 이름의 아티팩트로 저장되어 워크플로우 실행 결과에서 다운로드할 수 있습니다.
- **필수 설정**:
    - Gitea 저장소의 `Settings > Secrets` 및 `Settings > Actions`에 다음 변수들이 등록되어 있어야 합니다.
        - `GRAFANA_URL`
        - `GRAFANA_API_KEY` (Secret)
        - `MATTERMOST_WEBHOOK`
        - `GRAFANA_DASHBOARD_UID`
- **이메일 전송(선택)**:
    - 이메일 전송을 사용하려면 아래 설정을 추가합니다.
        - `SMTP_HOST`
        - `SMTP_PORT` (기본값: `587`)
        - `SMTP_USER`
        - `SMTP_PASSWORD` (Secret)
        - `EMAIL_RECIPIENTS` (쉼표 구분, 예: `devops@example.com,sre@example.com`)
    - `SMTP_HOST` 또는 `EMAIL_RECIPIENTS`가 없으면 이메일 전송은 자동으로 건너뜁니다.

### API 상태 확인 (`.gitea/workflows/health_check.yml`)

- **목적**: 특정 API 엔드포인트(`http://localhost:8000/health/API`)가 정상적으로 작동하는지 주기적으로 확인합니다.
- **동작**:
    - 1분마다 (`cron: '* * * * *'`) 스케줄에 따라 자동으로 실행됩니다.
    - `curl` 명령을 통해 API에 HTTP 요청을 보냅니다.
    - 응답이 `200 OK`가 아니거나 응답 내용에 "ok"가 포함되지 않으면 실패로 간주합니다.
    - 실패 시 10초 간격으로 최대 5번까지 재시도합니다.
    - 5번 연속 실패하면 Mattermost로 장애 알림 메시지를 전송합니다.
- **필수 설정**:
    - Gitea 저장소의 `Settings > Secrets`에 `MATTERMOST_WEBHOOK`이라는 이름으로 Mattermost 웹훅 URL이 등록되어 있어야 합니다.

## 시작하기

### 1. 사전 요구사항

- Docker
- Docker Compose

### 2. 설정

1.  **저장소 복제**
    ```bash
    git clone <repository_url>
    cd grafana_alerts
    ```

2.  **환경 변수 설정**
    `.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 파일 내의 변수들을 실제 환경에 맞게 수정합니다.
    ```bash
    cp .env.example .env
    ```
    - `GRAFANA_URL`: 사용하는 Grafana 인스턴스의 URL
    - `GRAFANA_API_KEY`: Grafana API에 접근하기 위한 API 키 (Viewer 역할 이상)
    - `GRAFANA_DASHBOARD_UID`: 리포트를 생성할 대상 대시보드의 UID
    - `MATTERMOST_WEBHOOK`: 리포트를 전송할 Mattermost 채널의 Incoming Webhook URL
    - `SMTP_HOST`: SMTP 서버 주소 (이메일 전송 사용 시)
    - `SMTP_PORT`: SMTP 서버 포트 (기본값 `587`)
    - `SMTP_USER`: SMTP 로그인 계정 (미설정 시 인증 없이 전송 시도)
    - `SMTP_PASSWORD`: SMTP 로그인 비밀번호 (Secret 권장)
    - `EMAIL_RECIPIENTS`: 이메일 수신자 목록 (쉼표로 구분)

3.  **Docker 이미지 빌드**
    ```bash
    docker compose build
    ```

### 3. 사용법

리포트를 생성하고 Mattermost/이메일로 전송하려면 아래의 `docker compose run` 명령어를 사용합니다.

-   **텍스트 형식 리포트 생성**
    ```bash
    docker compose run --rm reporter ./run_text.sh
    ```

-   **테이블 형식 리포트 생성**
    ```bash
    docker-compose run --rm reporter ./run_table.sh
    ```

`--rm` 플래그는 스크립트 실행 후 컨테이너를 자동으로 삭제하는 역할을 합니다.
