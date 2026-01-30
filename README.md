# Автоматизированный SDLC-пайплайн на основе LLM-агентов


При открытой Issue агент создаст ветку `agent/issue` и PR (`Fixes #N`).

## Модель
MODEL_NAME=google/gemma-3-12b-it:free (доступ через ключ OpenRouter)

## Как запустить
Надо создать Issue с задачей по доработке кода, агент сам запустит пайплайн и создаст PR.

## Как запустить локально

Рекомендуемые параметры для `.env`

```bash
LLM_PROVIDER=openai
MODEL_NAME=google/gemma-3-12b-it:free
BASE_BRANCH=main
MAX_ITERS=2
LLM_TEMPERATURE=0
LLM_TIMEOUT_SECONDS=90
```
Запуск в Docker

```bash
docker compose up -d --build
docker compose run --rm agent sdlc-agent run-issue --issue-number 1
```