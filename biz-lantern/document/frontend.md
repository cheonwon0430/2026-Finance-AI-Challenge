```bash
# =========================
# 1. Monorepo
# =========================

mkdir project-root
cd project-root

pnpm init

mkdir apps
mkdir packages

```YAML
# pnpm-workspace.yaml 작성

packages:
  - "apps/*"
  - "packages/*"

```

```bash
# =========================
# 2. Frontend
# =========================

pnpm create vite apps/frontend --template react-ts

cd apps/frontend

pnpm install
```

```bash

# =========================
# 3. Core
# =========================

pnpm add react-router
pnpm add zustand
pnpm add @tanstack/react-query
pnpm add axios
```

```bash
# =========================
# 4. UI
# =========================

pnpm add tailwindcss @tailwindcss/vite

pnpm dlx shadcn@latest init

pnpm add lucide-react
```

```bash
# =========================
# 5. Form / Validation
# =========================

pnpm add react-hook-form zod @hookform/resolvers
```

```bash
pnpm dev
```

## Frontend Stack
```plaintext
Frontend
│
├── React
├── TypeScript
├── Vite
│
├── React Router
├── Zustand
├── TanStack Query
├── Axios
│
├── Tailwind CSS
├── shadcn/ui
├── ReactBits      ← 필요할 때만
├── Lucide React
│
├── React Hook Form
├── Zod
│
├── ESLint
└── Prettier
```



src/
├── app/
│   ├── App.tsx
│   └── providers/
│
├── pages/
│   ├── Login/
│   └── Company/
│
├── domains/
│   ├── company/
│   │   ├── api/
│   │   ├── model/
│   │   ├── hooks/
│   │   └── components/
│   │
│   ├── auth/
│   │   ├── api/
│   │   ├── model/
│   │   ├── hooks/
│   │   └── components/
│   │
│   └── ...
│
└── shared/
    ├── api/
    │   └── axios.ts
    ├── components/
    ├── hooks/
    ├── utils/
    └── types/