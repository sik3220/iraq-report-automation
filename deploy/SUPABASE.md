# Supabase 연결

앱은 `DATABASE_URL`이 있을 때만 Supabase Postgres를 사용하고, 없으면 기존 SQLite로 동작합니다.

1. Supabase 프로젝트를 만들고 Connect에서 **Session pooler** 연결 문자열을 복사합니다.
2. 로컬 `.env`에 다음 값을 넣습니다. 비밀번호에 특수문자가 있으면 URL 인코딩합니다.

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@<pooler-host>:5432/postgres
```

3. 기존 로컬 DB를 백업한 뒤 데이터를 한 번 옮깁니다.

```powershell
Copy-Item data/articles.db data/articles-before-supabase.db
python scripts/migrate_to_supabase.py
```

4. 대시보드를 다시 시작하고 `/api/health`에서 `database`가 `supabase`인지 확인합니다.

수집기, 분석기, 대시보드는 같은 서버 전용 연결 문자열을 사용합니다. `DATABASE_URL`은 브라우저 코드나 GitHub 저장소에 넣지 않습니다.
