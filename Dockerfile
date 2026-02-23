# Python 3.9 슬림 버전을 기반 이미지로 사용
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 및 실행 스크립트 복사
COPY . .

# 스크립트에 실행 권한 부여
RUN chmod +x run_text.sh run_table.sh

# 기본적으로 아무것도 실행하지 않음 (docker-compose에서 커맨드 지정)
CMD ["tail", "-f", "/dev/null"]
