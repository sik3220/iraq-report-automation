This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## 주간 수집 파이프라인

보고 기간은 목요일부터 수요일까지 계산됩니다. 다음 명령을 실행하면 출처 수집, 중복 제거, 본문 재확보, 중요도 기반 AI 분류를 지정한 주간 범위 안에서 순서대로 처리합니다.

```bash
python scripts/run_weekly_pipeline.py --week-of 2026-09-08
```

특정 출처만 시험하려면 `--source ina --source reuters`처럼 반복 지정할 수 있습니다. 수집 단계는 AI를 호출하지 않으며, 중요도 기준을 통과한 기사만 분석 단계로 넘어갑니다.

## 대시보드 인증

배포 환경에서는 `.env.example`을 참고해 `DASHBOARD_PASSWORD`와 `AUTH_SECRET`를 서버 Secret 환경변수로 설정해야 합니다. 인증 설정이 없는 production 환경에서는 기사 API가 차단됩니다.

## Docker 배포

영속 디스크를 사용할 수 있는 서버에서 `.env`를 준비한 뒤 다음 명령으로 실행합니다.

```bash
docker compose up -d --build
```

`./data`가 컨테이너의 `/app/data`에 연결되므로 SQLite 기사 DB가 컨테이너 재생성 후에도 유지됩니다. 주간 수집은 별도 예약 작업에서 다음 명령을 실행합니다.

```bash
docker compose run --rm dashboard python scripts/run_weekly_pipeline.py
```

