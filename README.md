# Grafana 알림 리포터

Grafana, Prometheus, Loki 등에서 수집된 데이터를 기반으로 주기적인 요약 리포트를 생성하고 Mattermost/이메일로 전송하는 파이썬 기반 도구입니다.

## 주요 기능

- **데이터 소스 연동**: Grafana, Prometheus, Loki 데이터 소스에서 직접 데이터를 조회합니다.
- **자동 리포트 생성**: 지정된 Grafana 대시보드의 패널 쿼리를 실행하여 데이터를 요약하고 리포트를 생성합니다.
- **다양한 출력 형식**: 텍스트(Text) 및 테이블(Table) 형식의 리포트를 지원합니다.
- **Mattermost/이메일 통합**: 생성된 리포트를 Mattermost 웹훅 또는 SMTP 이메일로 자동 전송합니다.
- **API 상태 확인**: GitHub Actions를 통해 LLM/OCR API 상태를 주기적으로 확인하고 장애 발생 시 Mattermost로 알림을 전송합니다.
- **유연한 설정**: `.env` 파일을 통해 Grafana URL, API 키, 대시보드 UID 등의 설정을 쉽게 변경할 수 있습니다.

## 프로젝트 구조

```
.
├── .github/
│   └── workflows/
│       ├── main.yml               # 테이블 리포트 생성
│       ├── api_health_check.yml   # LLM-Gateway 상태 확인
│       └── ocr_health_check.yml   # OCR-Gateway 상태 확인
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

자동화는 `.github/workflows/`의 GitHub Actions 워크플로우로 실행합니다.

### 테이블 리포트 생성 (`.github/workflows/main.yml`)

- **실행 시각**: 매일 16:00 UTC, 한국시간 다음 날 01:00 (`cron: '0 16 * * *'`).
- **집계 기간**: 한국시간 기준 월요일에는 지난 7일(`run_table.sh 7d`), 그 외 요일에는 지난 24시간(`run_table.sh 24h`)을 요약합니다.
- **실행 환경**: `ubuntu-latest`에서 Python 의존성을 설치하고 `run_table.sh`를 실행합니다.
- **결과**: Mattermost/이메일로 리포트를 전송하며, `logs/table/*.log`는 `report-logs` 아티팩트로 업로드합니다(`actions/upload-artifact@v4`).

### LLM/OCR API 상태 확인

| 워크플로우 | 확인 대상 |
| :--- | :--- |
| `.github/workflows/api_health_check.yml` | LLM-Gateway: `http://localhost:8000/health/API` |
| `.github/workflows/ocr_health_check.yml` | OCR-Gateway: `http://localhost:8001/health/API` |

- 두 워크플로우 모두 `cron: '* * * * *'`로 설정되어 있습니다. 단, [GitHub Actions의 예약 실행 최소 간격은 5분](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)이므로 1분 주기 실행은 보장되지 않습니다.
- HTTP 상태가 `200`이고 응답 본문에 `ok`가 포함되면 정상으로 판단합니다.
- 실패 시 10초 간격으로 최대 5번 시도하고, 모두 실패하면 Mattermost로 알림을 보낸 뒤 작업을 실패 처리합니다.
- 현재 `runs-on: ubuntu-latest`이므로 `localhost`는 GitHub에서 제공하는 실행 서버 자체를 가리킵니다. 별도 서버의 API를 확인하려면 해당 서버에 접근 가능한 URL로 두 워크플로우의 요청 주소와 알림 문구를 수정해야 합니다. API가 설치된 서버에서 실행하려면 self-hosted runner 구성과 `runs-on` 변경이 필요합니다.

### GitHub Actions 설정

GitHub 저장소의 **Settings → Secrets and variables → Actions**에서 설정합니다. 워크플로우가 참조하는 위치에 맞게 **Variables**와 **Secrets**를 구분해 등록하세요.

| 이름 | 리포트 워크플로우 | 헬스체크 워크플로우 | 용도 |
| :--- | :--- | :--- | :--- |
| `GRAFANA_URL` | Variable | — | Grafana URL |
| `GRAFANA_API_KEY` | Secret | — | Grafana API 키 |
| `GRAFANA_DASHBOARD_UID` | Variable | — | 리포트 대상 대시보드 UID |
| `MATTERMOST_WEBHOOK` | Variable | Secret | Mattermost 웹훅 URL |
| `SMTP_HOST` | Variable | — | SMTP 서버 주소(이메일 사용 시) |
| `SMTP_PORT` | Variable | — | SMTP 포트(미설정 시 `587`) |
| `SMTP_USER` | Variable | — | SMTP 인증 사용자(선택) |
| `SMTP_PASSWORD` | Secret | — | SMTP 인증 비밀번호(필요 시) |
| `EMAIL_RECIPIENTS` | Variable | — | 수신자 목록(쉼표로 구분) |

현재 리포트 워크플로우는 `vars.MATTERMOST_WEBHOOK`, 헬스체크 워크플로우는 `secrets.MATTERMOST_WEBHOOK`을 사용하므로 두 기능을 모두 사용하려면 같은 이름으로 Variable과 Secret을 각각 등록해야 합니다.

`SMTP_HOST` 또는 `EMAIL_RECIPIENTS`가 없으면 이메일 전송은 건너뜁니다. 로컬 Docker 실행용 `.env` 설정은 GitHub Actions에 자동으로 적용되지 않습니다.

## 시작하기

### 1. 사전 요구사항

- Docker
- Docker Compose

### 2. 설정

1.  **저장소 복제**
    ```bash
    git clone https://github.com/Yongyeon-Kim/grafana-reporter.git
    cd grafana-reporter
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
    docker compose run --rm reporter ./run_table.sh
    ```

`--rm` 플래그는 스크립트 실행 후 컨테이너를 자동으로 삭제하는 역할을 합니다.
