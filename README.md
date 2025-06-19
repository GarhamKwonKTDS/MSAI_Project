# KT OSS-OM VoC 챗봇 시스템

KT OSS-OM(Operation Support System - Order Management)을 위한 포괄적인 고객의 소리(VoC) 챗봇 솔루션으로, 지능형 고객 지원 및 관리 기능을 제공합니다.

## 🚀 프로젝트 개요

이 프로젝트는 두 가지 주요 구성 요소로 이루어져 있습니다:

-   **챗봇 컴포넌트**: 고객으로부터 들어오는 VoC 요청을 처리하여 지능적인 가이드와 지원을 제공
-   **관리자 컴포넌트**: 관리자가 데이터베이스를 관리하고 대화 분석을 수행할 수 있도록 지원

## ✨ 핵심 기능

-   **다중 노드 LangGraph 구조**: VoC 요청이 적절히 처리되도록 후속 질문과 함께 체계적인 워크플로우 제공
-   **AI/LLM 지원 관리 대시보드**: 데이터셋 모니터링 및 개선을 위한 지능형 관리자 도구
-   **RAG with 벡터/의미론적 하이브리드 검색**: 관련 문서가 정확히 참조되도록 하는 검색 기능

## 🏗️ 아키텍처

### 인프라 구조 (Azure 클라우드 서비스)

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure 클라우드 플랫폼                       │
├─────────────────────────────────────────────────────────────┤
│ Azure App Services                                          │
│ ├── 챗봇 백엔드 서버 (Flask)                                    │
│ ├── 챗봇 프론트엔드 클라이언트 (JavaScript)                        │
│ ├── 관리자 백엔드 서버 (Flask)                                  │
│ └── 관리자 프론트엔드 클라이언트 (JavaScript)                      │
│                                                             │
│ Azure OpenAI Services                                       │
│ ├── LLM 배포: gpt-4o-mini                                    │
│ └── 임베딩 배포: text-embedding-3-small                        │
│                                                             │
│ Azure AI Search Service                                     │
│ └── 벡터 / 의미론적 하이브리드 검색                                │
│                                                             │
│ Azure Cosmos DB                                             │
│ └── 분석 데이터 저장소                                           │
└─────────────────────────────────────────────────────────────┘
```

### 시스템 연결 구조

**챗봇 시스템 흐름:**

```
챗봇 프론트엔드 → 챗봇 백엔드 API 호출
챗봇 백엔드 → Azure OpenAI + Search 서비스 (챗봇 기능)
챗봇 백엔드 → Azure Cosmos DB (대화 데이터 저장)
```

**관리자 시스템 흐름:**

```
관리자 프론트엔드 → 관리자 백엔드 API 호출
관리자 백엔드 → Azure OpenAI + Search 서비스 (에이전트 기능)
관리자 백엔드 → Azure Cosmos DB (분석 데이터 집계 및 조회)
```

## 🔄 LangGraph 워크플로우 개요

### 챗봇 백엔드 플로우

**새로운 주제/대화인 경우:**

```
상태 분석 → 이슈 분류 → 케이스 좁히기 → 응답 구성
```

**이미 식별된 이슈인 경우:**

```
상태 분석 → 케이스 좁히기 → 응답 구성
```

### 관리자 백엔드 플로우

```
상태 분석 → 요청 처리기
```

## 🛠️ 기술 스택

### 백엔드

-   **프레임워크**: Flask (Python)
-   **AI/ML**: Azure OpenAI Services
-   **검색**: Azure AI Search Service
-   **데이터베이스**: Azure Cosmos DB
-   **워크플로우**: LangGraph

### 프론트엔드

-   **언어**: JavaScript
-   **호스팅**: Azure App Services

### 클라우드 인프라

-   **플랫폼**: Microsoft Azure
-   **컴퓨팅**: Azure App Services
-   **AI 서비스**: Azure OpenAI
-   **검색 서비스**: Azure AI Search
-   **데이터베이스**: Azure Cosmos DB

## 📋 주요 기능

### 챗봇 기능

-   고객 VoC 요청 자동 처리
-   지능형 이슈 분류 및 케이스 분석
-   맥락 기반 응답 생성
-   대화 상태 관리
-   벡터 및 의미론적 검색 기반 정보 검색

### 관리자 기능

-   데이터베이스 관리
-   대화 분석 및 통계
-   시스템 모니터링
-   성능 분석 대시보드

## 🤖 LangGraph 워크플로우 설명

### 챗봇 백엔드 워크플로우

**새로운 주제/대화인 경우:**

-   State_Analysis → Issue_Classification → Case_Narrowing → Reply_Formulation

**이미 식별된 이슈인 경우:**

-   State_Analysis → Case_Narrowing → Reply_Formulation

### 관리자 백엔드 워크플로우

-   State_Analysis → Request_Handler

## 발표 자료

-   **데모 영상**: https://drive.google.com/drive/folders/1wwdB5R0oTGd7uLqf2L07bqXJMPYkyAA6?usp=sharing
-   **발표 자료**: https://www.miricanvas.com/v/14s4he3

## 설치 및 배포

### Deploy

```
./deploy_services.sh
./deploy_apps.sh
```

### Clean Up

```
./cleanup.sh
```

## 📞 지원 및 문의

프로젝트 관련 문의사항이나 기술 지원이 필요한 경우 OSS개발2팀 권가람 전임에게 연락해 주세요.
