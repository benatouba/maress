# MaRESS Maintainer Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Backend Deep Dive](#backend-deep-dive)
6. [Frontend Deep Dive](#frontend-deep-dive)
7. [Data Flow and Module Interactions](#data-flow-and-module-interactions)
8. [Development Workflow](#development-workflow)
9. [Testing Strategy](#testing-strategy)
10. [Database Management](#database-management)
11. [Common Maintenance Tasks](#common-maintenance-tasks)
12. [Troubleshooting Guide](#troubleshooting-guide)
13. [Deployment](#deployment)
14. [Contributing Guidelines](#contributing-guidelines)

---

## Project Overview

**MaRESS (Mapping Research in Earth System Sciences)** is a web application designed to help researchers map academic papers geographically. It automatically extracts geographic information from research papers using Natural Language Processing (NLP) and visualizes them on an interactive map.

### Key Features
- Integration with Zotero for paper management
- Automatic extraction of study sites from PDFs using NLP
- Interactive map visualization (OpenLayers)
- Graph-based relationship visualization (Cytoscape.js)
- Asynchronous task processing (Celery)
- User authentication and authorization

### Project Context
- **Funding:** German Research Foundation (NFDI4Earth, DFG project no. 460036893)
- **Authors:** Benjamin Rasmus Leander Schmidt & Marco Otto (TU Berlin)
- **License:** MIT

---

## Architecture Overview

MaRESS follows a modern **microservices-inspired architecture** with clear separation between frontend, backend, and processing services:

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         Nginx (Reverse Proxy)       │
└─────┬────────────────────┬──────────┘
      │                    │
      ▼                    ▼
┌─────────────┐    ┌──────────────┐
│  Frontend   │    │   Backend    │
│  (Vue 3)    │    │  (FastAPI)   │
└─────────────┘    └──────┬───────┘
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
        ┌──────────────┐    ┌─────────────┐
        │ PostgreSQL   │    │   Celery    │
        │ + PostGIS    │    │   Worker    │
        └──────────────┘    └──────┬──────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │    Redis     │
                            └──────────────┘
```

### Design Principles
1. **Separation of Concerns:** Frontend, backend, and workers handle distinct responsibilities
2. **Async Processing:** Long-running tasks (PDF extraction) run in background workers
3. **RESTful API:** Clear API contracts between frontend and backend
4. **Type Safety:** TypeScript in frontend, type hints in backend
5. **Database as Single Source of Truth:** All state persisted to PostgreSQL

---

## Technology Stack

### Frontend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Vue.js | 3.5+ | Reactive UI framework (Composition API) |
| TypeScript | 5.9+ | Type-safe JavaScript |
| Vuetify | 3.11+ | Material Design component library |
| Pinia | 3.0+ | State management |
| Vue Router | 4+ | Client-side routing |
| Vite | Latest | Build tool & dev server |
| OpenLayers | 10+ | Interactive maps |
| Cytoscape.js | 3.33+ | Graph visualization |
| Axios | 1+ | HTTP client |
| Chart.js | 4+ | Data visualization |

**Key Plugins:**
- `unplugin-vue-router` - File-based routing
- `unplugin-auto-import` - Auto-import Vue APIs
- `unplugin-vue-components` - Auto-import components

### Backend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Programming language |
| FastAPI | Latest | Web framework (ASGI) |
| SQLModel | Latest | ORM (SQLAlchemy + Pydantic) |
| PostgreSQL | 15 | Primary database |
| PostGIS | 3.3 | Geographic data extension |
| Redis | 7 | Cache & message broker |
| Celery | 5.6+ | Async task queue |
| spaCy | 3.7+ | NLP framework |
| scispacy | 0.6.2 | Scientific text processing |

**NLP & Document Processing:**
- `en_core_web_lg` - General English NLP model
- `en_core_web_trf` - Transformer-based model
- `en_core_sci_lg` - Scientific text model
- PyMuPDF (`fitz`) - PDF text extraction
- Camelot - Table extraction from PDFs
- tesserocr - OCR for scanned documents
- geopy - Geocoding location names

### Infrastructure

- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy & static file serving
- **uv** - Fast Python package manager
- **pnpm** - Fast Node.js package manager

---

## Project Structure

```
maress/
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   ├── alembic/      # Database migrations
│   │   │   └── versions/ # Migration files
│   │   ├── api/          # API routes
│   │   │   ├── routes/   # Endpoint definitions
│   │   │   │   ├── items.py
│   │   │   │   ├── study_sites.py
│   │   │   │   ├── tags.py
│   │   │   │   ├── users.py
│   │   │   │   └── login.py
│   │   │   ├── deps.py   # Dependency injection
│   │   │   └── main.py   # Router assembly
│   │   ├── core/         # Core configuration
│   │   │   ├── config.py # Settings (Pydantic)
│   │   │   ├── security.py # Auth & encryption
│   │   │   └── db.py     # Database session
│   │   ├── nlp/          # NLP pipeline
│   │   │   ├── orchestrator.py  # Main extraction pipeline
│   │   │   ├── extractors.py    # Entity extraction
│   │   │   ├── pdf_parser.py    # PDF processing
│   │   │   ├── geocoding.py     # Location → coordinates
│   │   │   ├── clustering.py    # Coordinate clustering
│   │   │   └── quality_assessment.py
│   │   ├── tasks/        # Celery tasks
│   │   │   ├── extract.py    # Study site extraction
│   │   │   └── download.py   # Zotero downloads
│   │   ├── email-templates/ # Email templates (MJML/HTML)
│   │   ├── model_factories/ # Factory patterns
│   │   ├── models.py     # Database models (SQLModel)
│   │   ├── crud.py       # Database operations
│   │   ├── services.py   # External services (Zotero)
│   │   ├── utils.py      # Utility functions
│   │   ├── main.py       # FastAPI app entry
│   │   └── celery_app.py # Celery configuration
│   ├── tests/            # Test suite
│   │   ├── api/          # API endpoint tests
│   │   ├── crud/         # CRUD operation tests
│   │   ├── nlp/          # NLP pipeline tests
│   │   └── data/         # Test data (PDFs, etc.)
│   ├── scripts/          # Utility scripts
│   │   ├── prestart.sh   # DB setup & migrations
│   │   ├── test.sh       # Run tests
│   │   ├── lint.sh       # Code linting
│   │   └── format.sh     # Code formatting
│   ├── pyproject.toml    # Python dependencies (uv)
│   ├── Dockerfile        # Container definition
│   └── README.md         # Backend documentation
│
├── frontend/             # Vue.js 3 frontend
│   ├── src/
│   │   ├── assets/       # Images, icons, etc.
│   │   ├── components/   # Vue components
│   │   │   ├── common/   # Reusable components
│   │   │   │   ├── BaseMap.vue
│   │   │   │   └── LoadingSpinner.vue
│   │   │   ├── layout/   # Layout components
│   │   │   │   ├── TopBar.vue
│   │   │   │   └── Footer.vue
│   │   │   ├── maps/     # Map components
│   │   │   │   ├── StudySiteMap.vue
│   │   │   │   ├── StudySiteEditDialog.vue
│   │   │   │   └── StudySiteCreateDialog.vue
│   │   │   └── papers/   # Paper components
│   │   │       ├── PaperCard.vue
│   │   │       ├── PaperList.vue
│   │   │       └── ExtractionResults.vue
│   │   ├── composables/  # Reusable logic
│   │   │   └── useGraphComposable.ts
│   │   ├── pages/        # Page components (auto-routed)
│   │   │   ├── index.vue      # Home
│   │   │   ├── Login.vue      # Login page
│   │   │   ├── Items.vue      # Papers list
│   │   │   ├── Map.vue        # Map view
│   │   │   ├── Graph.vue      # Graph view
│   │   │   └── Profile.vue    # User profile
│   │   ├── plugins/      # Vue plugins
│   │   │   ├── vuetify.ts    # Vuetify config
│   │   │   └── index.ts
│   │   ├── router/       # Vue Router
│   │   │   └── index.ts      # Route config
│   │   ├── services/     # API layer
│   │   │   ├── api.ts        # Axios instance
│   │   │   └── mapService.ts # Map utilities
│   │   ├── stores/       # Pinia stores
│   │   │   ├── auth.ts       # Authentication
│   │   │   ├── papers.ts     # Paper data
│   │   │   ├── tags.ts       # Tags
│   │   │   ├── studySites.ts # Study sites
│   │   │   ├── tasks.ts      # Task tracking
│   │   │   └── zotero.ts     # Zotero integration
│   │   ├── styles/       # SCSS styles
│   │   ├── utils/        # Utility functions
│   │   ├── App.vue       # Root component
│   │   └── main.ts       # App entry point
│   ├── tests/            # Frontend tests (Vitest)
│   ├── package.json      # Node dependencies (pnpm)
│   ├── vite.config.mts   # Vite configuration
│   ├── tsconfig.json     # TypeScript config
│   ├── Dockerfile        # Container definition
│   └── README.md         # Frontend documentation
│
├── nginx/                # Nginx configuration
│   └── nginx.conf        # Reverse proxy config
│
├── docker-compose.yml    # Development orchestration
├── docker-compose.prod.yml # Production orchestration
├── .env.example          # Environment template
├── CITATION.cff          # Citation metadata
├── LICENSE               # MIT license
└── README.md             # Main documentation
```

---

## Backend Deep Dive

### Core Architecture Pattern: Clean Architecture

The backend follows **Clean Architecture** principles with clear separation of concerns:

```
API Layer → CRUD Layer → Models Layer → Database
     ↓
Service Layer (External integrations)
     ↓
Task Layer (Async processing)
```

### Key Backend Modules

#### 1. Models Layer (`app/models.py`)

**Purpose:** Define database schema using SQLModel (combines SQLAlchemy ORM with Pydantic validation)

**Key Models:**

**User Model:**
```python
class User(SQLModel, table=True):
    id: uuid.UUID
    email: str  # unique, indexed
    hashed_password: str
    full_name: str
    is_active: bool = True
    is_superuser: bool = False
    zotero_id: str | None
    enc_zotero_api_key: str | None  # Encrypted with Fernet
    created_at: datetime
    updated_at: datetime
```

**Item Model (Research Paper):**
```python
class Item(SQLModel, table=True):
    id: uuid.UUID
    owner_id: uuid.UUID  # FK to User
    key: str  # Zotero key (8 chars, indexed)
    title: str
    abstractNote: str | None
    publicationTitle: str | None
    date: str | None
    doi: str | None
    url: str | None
    attachment: str | None  # PDF file path
    # ... many more metadata fields

    # Relationships
    creators: list["Creator"]
    tags: list["Tag"]
    study_sites: list["StudySite"]
```

**StudySite Model (Extracted Location):**
```python
class StudySite(SQLModel, table=True):
    id: uuid.UUID
    item_id: uuid.UUID  # FK to Item
    location_id: uuid.UUID  # FK to Location
    name: str
    context: str | None  # Sentence where found
    confidence_score: float | None
    validation_score: int | None  # User validation
    extraction_method: ExtractionMethod  # NER, PATTERN, TABLE, MANUAL
    source_type: SourceType  # TEXT, TABLE, METADATA
    section: Section  # ABSTRACT, METHODS, RESULTS, etc.
    is_manual: bool = False
```

**Location Model (Geographic Coordinates):**
```python
class Location(SQLModel, table=True):
    id: uuid.UUID
    latitude: float  # -90 to 90
    longitude: float  # -180 to 180
    cluster_label: int | None  # For DBSCAN clustering
```

**Model Pattern:**
- Base model (table=True): Database schema
- Create model: Fields required for creation
- Update model: All fields optional
- Public model: API response format

#### 2. CRUD Layer (`app/crud.py`)

**Purpose:** Abstract database operations from API routes

**Key Functions:**
```python
def create_user(*, session: Session, user_create: UserCreate) -> User
def get_user_by_email(*, session: Session, email: str) -> User | None
def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User
def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item
def create_study_site(*, session: Session, study_site_in: StudySiteCreate) -> StudySite
# ... many more
```

**Why CRUD Layer?**
- Keeps routes clean and focused on HTTP concerns
- Reusable across different endpoints
- Easier to test
- Single source of truth for database operations

#### 3. API Layer (`app/api/routes/`)

**Purpose:** Define HTTP endpoints, handle requests/responses

**Route Organization:**
- `login.py` - Authentication endpoints
- `users.py` - User management (CRUD)
- `items.py` - Paper management + Zotero sync
- `study_sites.py` - Study site CRUD
- `tags.py` - Tag management
- `utils.py` - Health checks, test endpoints

**Example Route:**
```python
@router.post("/", response_model=ItemPublic)
def create_item(
    *,
    session: SessionDep,  # Dependency injection
    current_user: CurrentUser,  # Auth check
    item_in: ItemCreate,
) -> Item:
    """Create new item."""
    item = crud.create_item(
        session=session,
        item_in=item_in,
        owner_id=current_user.id
    )
    return item
```

**Dependency Injection (`api/deps.py`):**
```python
SessionDep = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
```

#### 4. NLP Pipeline (`app/nlp/`)

**Purpose:** Extract geographic information from PDFs using Natural Language Processing

**Key Components:**

**Orchestrator (`orchestrator.py`):**
- Main entry point for extraction pipeline
- Coordinates all extraction steps
- Handles errors and retries

**Pipeline Flow:**
```
PDF → Text Extraction → Section Detection → Entity Extraction
   → Geocoding → Coordinate Clustering → Quality Assessment
   → Database Storage
```

**Extractors (`extractors.py`):**
1. **NER Extractor:** Uses spaCy to find GPE (Geo-Political Entity) named entities
2. **Pattern Extractor:** Regex patterns for coordinates (decimal degrees, DMS)
3. **Table Extractor:** Finds coordinates in tables (via Camelot)
4. **Spatial Relation Extractor:** Contextual clues ("located in", "study area in")

**PDF Parser (`pdf_parser.py`):**
- Extracts text using PyMuPDF (fitz)
- Falls back to OCR if needed (tesserocr, EasyOCR)
- Parses tables using Camelot
- Detects document sections (abstract, methods, results)

**Geocoding (`geocoding.py`):**
- Converts location names to coordinates
- Uses Nominatim (OpenStreetMap) via geopy
- Caches results to avoid repeated API calls
- Handles ambiguous locations

**Clustering (`clustering.py`):**
- Uses DBSCAN to cluster nearby coordinates
- Identifies primary study areas
- Removes outliers

**Quality Assessment (`quality_assessment.py`):**
- Scores extraction confidence
- Considers: extraction method, source type, section, context
- ML-based scoring (can be extended)

#### 5. Task Layer (`app/tasks/`)

**Purpose:** Long-running operations executed asynchronously via Celery

**Celery Configuration (`celery_app.py`):**
```python
celery = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,  # Redis
    backend=settings.CELERY_RESULT_BACKEND,  # Redis
)
```

**Key Tasks:**

**Extract Study Sites (`tasks/extract.py`):**
```python
@celery_app.task(bind=True)
def extract_study_sites_task(
    self,
    item_id: str,
    force_reextract: bool = False
) -> dict:
    # 1. Download PDF from Zotero
    # 2. Run NLP pipeline
    # 3. Save to database
    # 4. Update task progress
    return {"status": "success", "study_sites": [...]}
```

**Task Flow:**
1. User triggers extraction via API
2. API enqueues Celery task → Returns task_id
3. Frontend polls `/tasks/{task_id}/status`
4. Worker processes task in background
5. Task updates status in Redis
6. Frontend displays results when complete

#### 6. Service Layer (`app/services.py`)

**Purpose:** Integrate with external services (Zotero API)

**Zotero Integration:**
```python
def get_zotero_client(user: User) -> Zotero:
    # Decrypt API key
    api_key = decrypt_api_key(user.enc_zotero_api_key)
    return Zotero(
        library_id=user.zotero_id,
        library_type='user',
        api_key=api_key
    )

def sync_items_from_zotero(session: Session, user: User) -> list[Item]:
    # Fetch items from Zotero
    # Create/update in database
    # Return synced items
```

#### 7. Core Layer (`app/core/`)

**Configuration (`config.py`):**
```python
class Settings(BaseSettings):
    PROJECT_NAME: str = "MaRESS"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    # Database
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # Security
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Zotero
    ZOTERO_API_KEY: str | None
    ZOTERO_USER_ID: str | None

    # ... many more settings
```

**Security (`security.py`):**
- Password hashing: Argon2 via PWDLib
- JWT token generation/verification
- API key encryption: Fernet symmetric encryption
- CORS configuration

**Database (`db.py`):**
```python
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

---

## Frontend Deep Dive

### Core Architecture: Component-Based with Centralized State

```
Pages → Components → Stores → API Service → Backend
         ↓
    Composables (reusable logic)
```

### Key Frontend Modules

#### 1. Pages (`src/pages/`)

**Purpose:** Top-level route components (file-based routing)

**Key Pages:**
- `index.vue` - Home/dashboard
- `Login.vue` - Authentication
- `Items.vue` - Paper list with filters
- `Map.vue` - Interactive map view
- `Graph.vue` - Relationship graph
- `Tasks.vue` - Background task monitoring
- `Profile.vue` - User settings
- `Account.vue` - Account management

**Routing:** Auto-generated by `unplugin-vue-router` based on file structure

#### 2. Components (`src/components/`)

**Purpose:** Reusable UI components

**Component Organization:**

**Common Components (`components/common/`):**
- `BaseMap.vue` - OpenLayers map wrapper
- `LoadingSpinner.vue` - Loading indicator
- `TaskProgressBanner.vue` - Task status display

**Layout Components (`components/layout/`):**
- `TopBar.vue` - Navigation bar
- `Footer.vue` - Page footer

**Map Components (`components/maps/`):**
- `StudySiteMap.vue` - Map with study site markers
- `StudySiteEditDialog.vue` - Edit study site form
- `StudySiteCreateDialog.vue` - Create study site form

**Paper Components (`components/papers/`):**
- `PaperCard.vue` - Paper preview card
- `PaperList.vue` - Paginated paper list
- `ExtractionResults.vue` - Show all extraction candidates

**Component Pattern:**
```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { usePapersStore } from '@/stores/papers'

// Props
const props = defineProps<{
  paperId: string
}>()

// Emits
const emit = defineEmits<{
  updated: [paperId: string]
}>()

// Store
const papersStore = usePapersStore()

// Reactive state
const loading = ref(false)

// Computed properties
const paper = computed(() => papersStore.getById(props.paperId))

// Methods
async function updatePaper() {
  loading.value = true
  await papersStore.updatePaper(props.paperId, {...})
  emit('updated', props.paperId)
  loading.value = false
}
</script>

<template>
  <v-card>
    <!-- Template content -->
  </v-card>
</template>

<style scoped lang="scss">
// Scoped styles
</style>
```

#### 3. Stores (`src/stores/`)

**Purpose:** Centralized state management with Pinia

**Key Stores:**

**Auth Store (`stores/auth.ts`):**
```typescript
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  async function login(email: string, password: string) {
    const response = await api.post('/login/access-token', { email, password })
    token.value = response.data.access_token
    localStorage.setItem('token', token.value)
    await fetchUser()
  }

  async function fetchUser() {
    const response = await api.get('/users/me')
    user.value = response.data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { user, token, login, logout, fetchUser }
})
```

**Papers Store (`stores/papers.ts`):**
```typescript
export const usePapersStore = defineStore('papers', () => {
  const papers = ref<Item[]>([])
  const loading = ref(false)

  async function fetchPapers() {
    loading.value = true
    const response = await api.get('/items/')
    papers.value = response.data.items
    loading.value = false
  }

  async function syncZotero() {
    await api.post('/items/zotero/sync')
    await fetchPapers()
  }

  function getById(id: string) {
    return papers.value.find(p => p.id === id)
  }

  return { papers, loading, fetchPapers, syncZotero, getById }
})
```

**Other Stores:**
- `tags.ts` - Tag management
- `studySites.ts` - Study site data
- `tasks.ts` - Background task tracking
- `zotero.ts` - Zotero configuration
- `notification.ts` - Toast notifications
- `app.ts` - Global UI state (drawer, theme)

#### 4. Services (`src/services/`)

**Purpose:** API communication layer

**API Service (`services/api.ts`):**
```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_V1_URL || '/api/v1',
  timeout: 30000,
})

// Request interceptor: Add auth token
api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

// Response interceptor: Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default api
```

**Map Service (`services/mapService.ts`):**
- OpenLayers utilities
- Map layer creation
- Marker styling

#### 5. Composables (`src/composables/`)

**Purpose:** Reusable reactive logic (Vue 3 Composition API pattern)

**Example: Graph Composable (`composables/useGraphComposable.ts`):**
```typescript
export function useGraph(containerRef: Ref<HTMLElement | null>) {
  const cy = ref<Core | null>(null)

  function initializeGraph() {
    cy.value = cytoscape({
      container: containerRef.value,
      elements: [],
      style: [...],
      layout: { name: 'fcose' }
    })
  }

  function addNode(node: Node) {
    cy.value?.add({ data: node })
  }

  function applyLayout(layoutName: string) {
    cy.value?.layout({ name: layoutName }).run()
  }

  return { cy, initializeGraph, addNode, applyLayout }
}
```

#### 6. Router (`src/router/`)

**Purpose:** Client-side routing

**Auto-Generated Routes:**
```typescript
// Generated by unplugin-vue-router from src/pages/
const routes = [
  { path: '/', component: () => import('@/pages/index.vue') },
  { path: '/login', component: () => import('@/pages/Login.vue') },
  { path: '/items', component: () => import('@/pages/Items.vue'), meta: { requiresAuth: true } },
  // ...
]
```

**Auth Guard:**
```typescript
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.token) {
    next('/login')
  } else {
    next()
  }
})
```

#### 7. Plugins (`src/plugins/`)

**Vuetify Configuration (`plugins/vuetify.ts`):**
```typescript
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          primary: '#1976D2',
          secondary: '#424242',
          // ...
        }
      }
    }
  }
})
```

---

## Data Flow and Module Interactions

### 1. User Authentication Flow

```
User enters credentials → Login.vue
  ↓
authStore.login(email, password)
  ↓
POST /api/v1/login/access-token
  ↓
Backend: Verify credentials (security.py)
  ↓
Generate JWT token
  ↓
Response: { access_token: "..." }
  ↓
Frontend: Store token in localStorage
  ↓
authStore.fetchUser() → GET /api/v1/users/me
  ↓
Store user data in authStore.user
  ↓
Redirect to home page
```

### 2. Paper Sync Flow

```
User clicks "Sync Zotero" → Items.vue
  ↓
papersStore.syncZotero()
  ↓
POST /api/v1/items/zotero/sync
  ↓
Backend: services.sync_items_from_zotero()
  ↓
Decrypt user's Zotero API key (security.py)
  ↓
Fetch items from Zotero API (pyzotero)
  ↓
For each item:
  - Check if exists in DB
  - Create/update via crud.create_item()
  - Save creators, tags, collections
  ↓
Return synced items
  ↓
Frontend: papersStore.fetchPapers() → Update UI
```

### 3. Study Site Extraction Flow

```
User clicks "Extract Study Sites" → Item detail page
  ↓
tasksStore.extractStudySites(itemId)
  ↓
POST /api/v1/items/extract-study-sites
  ↓
Backend: Enqueue Celery task
  ↓
tasks.extract.extract_study_sites_task.delay(item_id)
  ↓
Return task_id
  ↓
Frontend: Start polling GET /api/v1/tasks/{task_id}/status
  ↓
Celery Worker picks up task:
  1. Fetch Item from DB
  2. Download PDF if needed (download_attachment_from_zotero)
  3. Run NLP pipeline (orchestrator.extract_study_sites)
     a. Parse PDF (pdf_parser.extract_text_from_pdf)
     b. Detect sections (orchestrator.detect_sections)
     c. Extract entities (extractors.NERExtractor)
     d. Extract coordinates (extractors.PatternExtractor)
     e. Parse tables (pdf_parser.extract_tables)
     f. Geocode location names (geocoding.geocode_location)
     g. Cluster coordinates (clustering.cluster_coordinates)
     h. Score quality (quality_assessment.assess_quality)
  4. Save StudySites to DB (via adapters)
  5. Update task status: SUCCESS
  ↓
Frontend: Poll receives "SUCCESS" status
  ↓
studySitesStore.fetchStudySites(itemId)
  ↓
Update map markers
```

### 4. Map Visualization Flow

```
User navigates to Map page → Map.vue
  ↓
studySitesStore.fetchStudySites()
  ↓
GET /api/v1/study-sites/
  ↓
Backend: Query StudySites with Location joins
  ↓
Return study sites with coordinates
  ↓
Frontend: BaseMap.vue receives study sites
  ↓
mapService.createMarkers(studySites)
  ↓
OpenLayers renders markers on map
  ↓
User clicks marker → Show popup with paper details
  ↓
Click "Edit" → StudySiteEditDialog.vue
  ↓
User updates location → studySitesStore.updateStudySite()
  ↓
PATCH /api/v1/study-sites/{id}
  ↓
Backend: crud.update_study_site()
  ↓
Frontend: Refresh map markers
```

### 5. Graph Visualization Flow

```
User navigates to Graph page → Graph.vue
  ↓
Fetch papers, creators, study sites
  ↓
useGraphComposable.initializeGraph()
  ↓
Build graph data:
  - Nodes: papers, authors, locations
  - Edges: authorship, co-authorship, shared locations
  ↓
cytoscape.add(elements)
  ↓
Apply layout algorithm (fcose or dagre)
  ↓
User clicks node → Show NodeInfoDialog.vue
  ↓
User filters by node type → Rebuild graph
```

---

## Development Workflow

### Initial Setup

#### Backend Setup

1. **Clone repository:**
   ```bash
   git clone <repo-url>
   cd maress/backend
   ```

2. **Install dependencies:**
   ```bash
   # Install uv (if not installed)
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv sync
   ```

3. **Download spaCy models:**
   ```bash
   uv run python -m spacy download en_core_web_lg
   uv run python -m spacy download en_core_web_trf
   uv run pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz
   ```

4. **Configure environment:**
   ```bash
   cp ../.env.example ../.env.local
   # Edit .env.local with your settings
   ```

5. **Start dependencies (Docker):**
   ```bash
   docker-compose up -d db redis
   ```

6. **Initialize database:**
   ```bash
   bash scripts/prestart.sh
   # This runs migrations and creates superuser
   ```

7. **Run backend:**
   ```bash
   uv run fastapi run --reload
   # API available at http://localhost:8000
   # Docs at http://localhost:8000/docs
   ```

8. **Run Celery worker (separate terminal):**
   ```bash
   uv run celery -A app.celery_app worker --loglevel=info --concurrency=2
   ```

#### Frontend Setup

1. **Navigate to frontend:**
   ```bash
   cd maress/frontend
   ```

2. **Install pnpm (if not installed):**
   ```bash
   npm install -g pnpm
   ```

3. **Install dependencies:**
   ```bash
   pnpm install
   ```

4. **Run dev server:**
   ```bash
   pnpm run dev
   # Available at http://localhost:3000
   ```

### Development with Docker

**Start all services:**
```bash
docker-compose up --build
```

**Watch mode (auto-rebuild):**
```bash
docker-compose watch
```

**Services:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Backend Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- MailHog (email testing): http://localhost:8025

### Daily Development Tasks

#### Making Backend Changes

1. **Create feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes to code**

3. **Run tests:**
   ```bash
   uv run pytest
   # Or with coverage
   bash scripts/test.sh
   ```

4. **Run linting:**
   ```bash
   bash scripts/lint.sh
   ```

5. **Format code:**
   ```bash
   bash scripts/format.sh
   ```

6. **If models changed, create migration:**
   ```bash
   uv run alembic revision --autogenerate -m "Add new field to Item"
   # Review generated migration in app/alembic/versions/
   uv run alembic upgrade head
   ```

7. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

#### Making Frontend Changes

1. **Create feature branch** (if not already)

2. **Make changes to components/pages**

3. **Run tests:**
   ```bash
   pnpm run test
   ```

4. **Type check:**
   ```bash
   pnpm run type-check
   ```

5. **Lint:**
   ```bash
   pnpm run lint
   ```

6. **Format:**
   ```bash
   pnpm run format
   ```

7. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: add new component"
   ```

### Testing Strategy

#### Backend Testing

**Test Organization:**
```
tests/
├── api/              # API endpoint tests
│   ├── test_items.py
│   ├── test_users.py
│   └── test_study_sites.py
├── crud/             # Database operation tests
│   ├── test_item_crud.py
│   └── test_user_crud.py
├── nlp/              # NLP pipeline tests
│   ├── test_clustering.py
│   ├── test_extractors.py
│   └── test_orchestrator.py
└── data/             # Test fixtures (PDFs, etc.)
```

**Running Tests:**
```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/api/test_items.py

# Specific test
uv run pytest tests/api/test_items.py::test_create_item

# With coverage
uv run pytest --cov=app --cov-report=html

# Watch mode
uv run pytest --watch
```

**Writing Tests:**
```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

def test_create_item(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session
) -> None:
    """Test creating a new item."""
    data = {
        "title": "Test Paper",
        "abstractNote": "Test abstract",
        "key": "TESTKEY1"
    }
    response = client.post(
        "/api/v1/items/",
        headers=superuser_token_headers,
        json=data
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert "id" in content
```

#### Frontend Testing

**Test Organization:**
```
src/tests/
├── components/
│   ├── PaperCard.spec.ts
│   └── StudySiteMap.spec.ts
└── stores/
    ├── auth.spec.ts
    └── papers.spec.ts
```

**Running Tests:**
```bash
# All tests
pnpm run test

# Watch mode
pnpm run test:watch

# UI mode
pnpm run test:ui

# Coverage
pnpm run test:coverage
```

**Writing Tests:**
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PaperCard from '@/components/papers/PaperCard.vue'

describe('PaperCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders paper title', () => {
    const wrapper = mount(PaperCard, {
      props: {
        paper: {
          id: '123',
          title: 'Test Paper',
          abstractNote: 'Test abstract'
        }
      }
    })
    expect(wrapper.text()).toContain('Test Paper')
  })

  it('emits delete event when delete button clicked', async () => {
    const wrapper = mount(PaperCard, { props: { paper: {...} } })
    await wrapper.find('.delete-btn').trigger('click')
    expect(wrapper.emitted('delete')).toBeTruthy()
  })
})
```

---

## Database Management

### Schema Overview

**Core Tables:**
1. `user` - User accounts
2. `item` - Research papers (from Zotero)
3. `creator` - Paper authors (1:M with Item)
4. `tag` - Paper tags
5. `itemtaglink` - Many-to-many Item-Tag relationship
6. `location` - Geographic coordinates
7. `studysite` - Extracted study sites (M:1 with Location)
8. `extractionresult` - All extraction candidates (not just top 10)
9. `collection` - Zotero collections
10. `relation` - Item relationships (citations, etc.)

### Migrations with Alembic

**Migration Workflow:**

1. **Make model changes** in `app/models.py`

2. **Generate migration:**
   ```bash
   uv run alembic revision --autogenerate -m "Description of change"
   ```

3. **Review generated migration** in `app/alembic/versions/`:
   ```python
   def upgrade() -> None:
       # Review these changes carefully
       op.add_column('item', sa.Column('new_field', sa.String(), nullable=True))

   def downgrade() -> None:
       op.drop_column('item', 'new_field')
   ```

4. **Apply migration:**
   ```bash
   uv run alembic upgrade head
   ```

5. **Rollback if needed:**
   ```bash
   uv run alembic downgrade -1  # One step back
   uv run alembic downgrade <revision_id>  # To specific revision
   ```

**Migration Best Practices:**
- Always review auto-generated migrations
- Test migrations on a copy of production data
- Write both `upgrade()` and `downgrade()` functions
- Add data migrations when needed (not just schema)
- Use `op.batch_alter_table()` for SQLite compatibility (if needed)

**Check current revision:**
```bash
uv run alembic current
```

**View migration history:**
```bash
uv run alembic history
```

### Database Backup and Restore

**Backup (Docker):**
```bash
docker-compose exec db pg_dump -U maress maress > backup_$(date +%Y%m%d).sql
```

**Restore (Docker):**
```bash
docker-compose exec -T db psql -U maress maress < backup_20240101.sql
```

**Manual backup (local PostgreSQL):**
```bash
pg_dump -h localhost -U maress -d maress -f backup.sql
```

### Database Console Access

**Via Docker:**
```bash
docker-compose exec db psql -U maress maress
```

**Via local client:**
```bash
psql postgresql://maress:password@localhost:5432/maress
```

**Useful queries:**
```sql
-- Count items by user
SELECT owner_id, COUNT(*) FROM item GROUP BY owner_id;

-- Items without study sites
SELECT id, title FROM item WHERE NOT EXISTS (
    SELECT 1 FROM studysite WHERE studysite.item_id = item.id
);

-- Study sites by extraction method
SELECT extraction_method, COUNT(*) FROM studysite GROUP BY extraction_method;

-- Average confidence score
SELECT AVG(confidence_score) FROM studysite WHERE confidence_score IS NOT NULL;
```

---

## Common Maintenance Tasks

### 1. Adding a New API Endpoint

**Step 1: Define route**
```python
# backend/app/api/routes/items.py

@router.get("/{id}/summary")
def get_item_summary(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID
) -> dict:
    """Get summary statistics for an item."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    study_site_count = len(item.study_sites)
    tag_count = len(item.tags)

    return {
        "id": item.id,
        "study_site_count": study_site_count,
        "tag_count": tag_count
    }
```

**Step 2: Add to frontend service**
```typescript
// frontend/src/services/api.ts

export async function getItemSummary(itemId: string) {
  const response = await api.get(`/items/${itemId}/summary`)
  return response.data
}
```

**Step 3: Use in component**
```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getItemSummary } from '@/services/api'

const props = defineProps<{ itemId: string }>()
const summary = ref(null)

onMounted(async () => {
  summary.value = await getItemSummary(props.itemId)
})
</script>

<template>
  <div v-if="summary">
    <p>Study Sites: {{ summary.study_site_count }}</p>
    <p>Tags: {{ summary.tag_count }}</p>
  </div>
</template>
```

### 2. Adding a New Database Field

**Step 1: Update model**
```python
# backend/app/models.py

class Item(SQLModel, table=True):
    # Existing fields...
    is_favorite: bool = False  # New field
```

**Step 2: Update schemas**
```python
# If field should be settable on creation
class ItemCreate(ItemBase):
    is_favorite: bool = False

# If field should be updatable
class ItemUpdate(ItemBase):
    is_favorite: bool | None = None

# Public schema automatically includes new field
```

**Step 3: Create migration**
```bash
uv run alembic revision --autogenerate -m "Add is_favorite to Item"
```

**Step 4: Review and apply**
```bash
# Review file in app/alembic/versions/
uv run alembic upgrade head
```

**Step 5: Update frontend types**
```typescript
// frontend/src/types/api.ts (if exists)
export interface Item {
  id: string
  title: string
  // ... existing fields
  is_favorite: boolean  // New field
}
```

### 3. Adding a New Vue Component

**Step 1: Create component file**
```bash
touch frontend/src/components/papers/PaperFilters.vue
```

**Step 2: Implement component**
```vue
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  filterChange: [filters: FilterOptions]
}>()

const searchQuery = ref('')
const selectedTags = ref<string[]>([])

function applyFilters() {
  emit('filterChange', {
    search: searchQuery.value,
    tags: selectedTags.value
  })
}
</script>

<template>
  <v-card>
    <v-card-title>Filters</v-card-title>
    <v-card-text>
      <v-text-field
        v-model="searchQuery"
        label="Search"
        @update:model-value="applyFilters"
      />
      <!-- More filter controls -->
    </v-card-text>
  </v-card>
</template>
```

**Step 3: Use in parent component**
```vue
<script setup lang="ts">
import PaperFilters from '@/components/papers/PaperFilters.vue'  // Auto-imported if using unplugin-vue-components

function handleFilterChange(filters: FilterOptions) {
  // Apply filters
}
</script>

<template>
  <PaperFilters @filter-change="handleFilterChange" />
</template>
```

### 4. Adding a New Pinia Store

**Step 1: Create store file**
```typescript
// frontend/src/stores/favorites.ts

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useFavoritesStore = defineStore('favorites', () => {
  const favoriteIds = ref<Set<string>>(new Set())
  const loading = ref(false)

  const count = computed(() => favoriteIds.value.size)

  async function fetchFavorites() {
    loading.value = true
    try {
      const response = await api.get('/items/', { params: { is_favorite: true } })
      favoriteIds.value = new Set(response.data.items.map(item => item.id))
    } finally {
      loading.value = false
    }
  }

  async function toggleFavorite(itemId: string) {
    const isFavorite = favoriteIds.value.has(itemId)
    await api.patch(`/items/${itemId}`, { is_favorite: !isFavorite })

    if (isFavorite) {
      favoriteIds.value.delete(itemId)
    } else {
      favoriteIds.value.add(itemId)
    }
  }

  function isFavorite(itemId: string) {
    return favoriteIds.value.has(itemId)
  }

  return { favoriteIds, loading, count, fetchFavorites, toggleFavorite, isFavorite }
})
```

**Step 2: Use in component**
```vue
<script setup lang="ts">
import { useFavoritesStore } from '@/stores/favorites'

const favoritesStore = useFavoritesStore()

onMounted(() => {
  favoritesStore.fetchFavorites()
})
</script>

<template>
  <v-btn @click="favoritesStore.toggleFavorite(itemId)">
    <v-icon>{{ favoritesStore.isFavorite(itemId) ? 'mdi-star' : 'mdi-star-outline' }}</v-icon>
  </v-btn>
</template>
```

### 5. Adding a New Celery Task

**Step 1: Define task**
```python
# backend/app/tasks/analyze.py

from app.celery_app import celery_app
from app.models import Item
from app.core.db import get_session

@celery_app.task(bind=True)
def analyze_item_content(self, item_id: str) -> dict:
    """Analyze item content for keywords, topics, etc."""
    self.update_state(state='PROGRESS', meta={'status': 'Analyzing...'})

    with next(get_session()) as session:
        item = session.get(Item, item_id)
        if not item:
            return {"status": "error", "message": "Item not found"}

        # Perform analysis
        keywords = extract_keywords(item.abstractNote)
        topics = classify_topics(item.abstractNote)

        # Save results to database
        item.analysis_keywords = keywords
        item.analysis_topics = topics
        session.add(item)
        session.commit()

        return {
            "status": "success",
            "keywords": keywords,
            "topics": topics
        }
```

**Step 2: Add API endpoint to trigger task**
```python
# backend/app/api/routes/items.py

@router.post("/{id}/analyze")
def analyze_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    background_tasks: BackgroundTasks
) -> dict:
    """Trigger content analysis for an item."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    task = analyze_item_content.delay(str(id))
    return {"task_id": task.id}
```

**Step 3: Add frontend method**
```typescript
// In store or component
async function analyzeItem(itemId: string) {
  const response = await api.post(`/items/${itemId}/analyze`)
  const taskId = response.data.task_id

  // Poll for task status
  return pollTaskStatus(taskId)
}
```

### 6. Updating NLP Extraction Logic

**Example: Add new pattern for coordinates**

```python
# backend/app/nlp/pattern_registry.py

# Add to existing patterns
NEW_PATTERN = r'(?:N|S)\s*(\d{1,2})[°]\s*(\d{1,2})[\']\s*(\d{1,2}\.?\d*)["]\s*(?:E|W)\s*(\d{1,3})[°]\s*(\d{1,2})[\']\s*(\d{1,2}\.?\d*)[""]'

COORDINATE_PATTERNS.append(NEW_PATTERN)
```

```python
# backend/app/nlp/extractors.py

class PatternExtractor:
    def extract(self, text: str) -> list[ExtractionCandidate]:
        candidates = []

        # Existing patterns...

        # Add new pattern matching
        for match in re.finditer(NEW_PATTERN, text):
            lat = self._dms_to_decimal(match.group(1), match.group(2), match.group(3))
            lon = self._dms_to_decimal(match.group(4), match.group(5), match.group(6))
            candidates.append(ExtractionCandidate(
                name=f"{lat:.4f}, {lon:.4f}",
                latitude=lat,
                longitude=lon,
                confidence_score=0.9,
                extraction_method=ExtractionMethod.PATTERN
            ))

        return candidates
```

**Test new pattern:**
```python
# backend/tests/nlp/test_extractors.py

def test_new_coordinate_pattern():
    extractor = PatternExtractor()
    text = "Study area located at N 52° 31' 12.5\" E 13° 24' 18.0\""
    candidates = extractor.extract(text)

    assert len(candidates) > 0
    assert candidates[0].latitude == pytest.approx(52.52013889, rel=1e-5)
    assert candidates[0].longitude == pytest.approx(13.405, rel=1e-5)
```

---

## Troubleshooting Guide

### Backend Issues

#### Database Connection Errors

**Symptom:** `sqlalchemy.exc.OperationalError: could not connect to server`

**Causes & Solutions:**
1. PostgreSQL not running:
   ```bash
   docker-compose ps db
   docker-compose up -d db
   ```

2. Wrong credentials in `.env.local`:
   ```bash
   # Check these match docker-compose.yml
   POSTGRES_SERVER=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=maress
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=maress
   ```

3. Database not initialized:
   ```bash
   bash scripts/prestart.sh
   ```

#### Celery Worker Not Processing Tasks

**Symptom:** Tasks stay in PENDING state forever

**Causes & Solutions:**
1. Worker not running:
   ```bash
   # Terminal 1: Check worker logs
   docker-compose logs -f worker

   # Terminal 2: Start worker if not running
   uv run celery -A app.celery_app worker --loglevel=info
   ```

2. Redis not running:
   ```bash
   docker-compose up -d redis
   ```

3. Wrong broker URL:
   ```bash
   # .env.local
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   ```

4. Worker crashed on startup:
   ```bash
   # Check for import errors
   uv run celery -A app.celery_app worker --loglevel=debug
   ```

#### PDF Extraction Failing

**Symptom:** Task completes but no study sites extracted

**Causes & Solutions:**
1. PDF file missing:
   ```python
   # Check attachment path exists
   item = session.get(Item, item_id)
   print(item.attachment)  # Should be valid file path
   ```

2. spaCy models not installed:
   ```bash
   uv run python -c "import spacy; spacy.load('en_core_web_lg')"
   # If error, reinstall:
   uv run python -m spacy download en_core_web_lg
   ```

3. OCR dependencies missing:
   ```bash
   # Install system dependencies (Ubuntu/Debian)
   sudo apt-get install -y ghostscript tesseract-ocr libtesseract-dev
   ```

4. PDF is scanned (image-based):
   - Check OCR is working:
   ```python
   from app.nlp.pdf_parser import extract_text_from_pdf
   text = extract_text_from_pdf('path/to/pdf', use_ocr=True)
   print(len(text))  # Should be > 0
   ```

#### Import Errors After Adding New Dependency

**Symptom:** `ModuleNotFoundError: No module named 'xxx'`

**Solution:**
```bash
# Ensure dependency added to pyproject.toml
uv add package-name

# Sync virtual environment
uv sync

# Verify installation
uv run python -c "import package_name"
```

### Frontend Issues

#### Components Not Auto-Importing

**Symptom:** `Cannot find module '@/components/xxx' or its corresponding type declarations`

**Solution:**
1. Check component file name matches usage (case-sensitive)
2. Restart Vite dev server:
   ```bash
   # Ctrl+C to stop
   pnpm run dev
   ```
3. Check `vite.config.mts` has `unplugin-vue-components` configured

#### API Requests Failing with CORS Error

**Symptom:** `Access to XMLHttpRequest blocked by CORS policy`

**Solutions:**
1. Check backend CORS settings:
   ```python
   # backend/app/core/config.py
   BACKEND_CORS_ORIGINS: list[str] = [
       "http://localhost:3000",  # Must match frontend URL
   ]
   ```

2. Restart backend after changing CORS settings

3. Check Vite proxy configuration:
   ```typescript
   // frontend/vite.config.mts
   server: {
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
       }
     }
   }
   ```

#### Vuetify Components Not Styling Correctly

**Symptom:** Components render but lack Material Design styling

**Solutions:**
1. Check Vuetify plugin imported in `main.ts`:
   ```typescript
   import vuetify from './plugins/vuetify'
   app.use(vuetify)
   ```

2. Check styles imported:
   ```typescript
   import 'vuetify/styles'
   ```

3. Clear Vite cache:
   ```bash
   rm -rf node_modules/.vite
   pnpm run dev
   ```

#### Type Errors in TypeScript

**Symptom:** `Property 'xxx' does not exist on type 'yyy'`

**Solutions:**
1. Update type definitions:
   ```typescript
   // src/types/api.ts
   export interface Item {
     id: string
     title: string
     xxx: string  // Add missing property
   }
   ```

2. Run type checker:
   ```bash
   pnpm run type-check
   ```

3. If auto-imports not working, manually import types:
   ```typescript
   import type { Item } from '@/types/api'
   ```

### Docker Issues

#### Container Won't Start

**Symptom:** `docker-compose up` fails with error

**Solutions:**
1. Check logs:
   ```bash
   docker-compose logs service-name
   ```

2. Rebuild containers:
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up
   ```

3. Check port conflicts:
   ```bash
   # Check if port 8000 already in use
   lsof -i :8000
   # Kill process or change port in docker-compose.yml
   ```

4. Disk space issues:
   ```bash
   docker system df  # Check disk usage
   docker system prune  # Clean up unused containers/images
   ```

#### Container Running but Service Unavailable

**Symptom:** Container shows as "Up" but can't connect

**Solutions:**
1. Check container health:
   ```bash
   docker-compose ps
   docker-compose exec service-name curl http://localhost:8000/api/v1/utils/health-check
   ```

2. Check network:
   ```bash
   docker-compose exec service-name ping other-service
   ```

3. Check environment variables:
   ```bash
   docker-compose exec service-name env | grep POSTGRES
   ```

---

## Deployment

### Production Deployment Checklist

#### Pre-Deployment

- [ ] Set strong passwords in `.env.production`
  - [ ] `SECRET_KEY` - Generate: `openssl rand -hex 32`
  - [ ] `ENCRYPTION_KEY` - Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  - [ ] `POSTGRES_PASSWORD` - Strong random password
  - [ ] `FIRST_SUPERUSER_PASSWORD` - Strong admin password

- [ ] Configure SMTP for email notifications
  ```bash
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your-email@gmail.com
  SMTP_PASSWORD=your-app-password
  EMAILS_FROM_EMAIL=noreply@yourdomain.com
  ```

- [ ] Set environment to production
  ```bash
  ENVIRONMENT=production
  ```

- [ ] Update CORS origins
  ```python
  BACKEND_CORS_ORIGINS=["https://yourdomain.com"]
  ```

- [ ] Configure SSL certificates (add to `nginx/`)
  ```nginx
  ssl_certificate /etc/nginx/ssl/fullchain.pem;
  ssl_certificate_key /etc/nginx/ssl/privkey.pem;
  ```

- [ ] Review and update `docker-compose.prod.yml`

#### Deployment Steps

1. **Clone repository on server:**
   ```bash
   git clone <repo-url> /var/www/maress
   cd /var/www/maress
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env.production
   nano .env.production  # Edit with production values
   ```

3. **Build and start services:**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Initialize database:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec backend bash scripts/prestart.sh
   ```

5. **Verify services:**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   curl https://yourdomain.com/api/v1/utils/health-check
   ```

#### Post-Deployment

- [ ] Set up log rotation
- [ ] Configure backups (see Database Backup section)
- [ ] Set up monitoring (e.g., Prometheus, Grafana)
- [ ] Configure firewall rules
- [ ] Test error reporting (Sentry, etc.)

### Environment-Specific Configuration

#### Local Development
- Debug enabled
- MailHog for email testing
- Hot reload for frontend/backend
- Verbose logging

#### Staging
- Similar to production
- Test SMTP configuration
- Test with production-like data
- Performance testing

#### Production
- Optimized builds
- Real SMTP for emails
- No debug mode
- Error tracking (Sentry)
- Log aggregation
- Automated backups

### Monitoring

**Check service health:**
```bash
# All services status
docker-compose ps

# Backend health
curl http://localhost:8000/api/v1/utils/health-check

# Check logs
docker-compose logs -f --tail=100 backend
docker-compose logs -f --tail=100 worker
docker-compose logs -f --tail=100 frontend
```

**Monitor resource usage:**
```bash
docker stats
```

**Monitor Celery tasks:**
```bash
docker-compose exec worker celery -A app.celery_app inspect active
docker-compose exec worker celery -A app.celery_app inspect stats
```

---

## Contributing Guidelines

### Code Style

#### Backend (Python)

**Formatting:**
- Use `ruff` for linting and formatting
- Line length: 88 characters (Black default)
- Run before commit:
  ```bash
  bash scripts/format.sh
  bash scripts/lint.sh
  ```

**Conventions:**
- Use type hints for all function parameters and return values
- Document functions with docstrings (Google style)
- Use descriptive variable names
- Prefer composition over inheritance
- Follow SOLID principles

**Example:**
```python
def create_item(
    *,
    session: Session,
    item_in: ItemCreate,
    owner_id: uuid.UUID
) -> Item:
    """
    Create a new item in the database.

    Args:
        session: Database session
        item_in: Item creation schema
        owner_id: ID of the item owner

    Returns:
        Created item instance

    Raises:
        ValueError: If item with same key already exists
    """
    # Implementation
```

#### Frontend (TypeScript/Vue)

**Formatting:**
- Use Prettier for formatting
- ESLint with Vue/TypeScript rules
- Run before commit:
  ```bash
  pnpm run format
  pnpm run lint
  ```

**Conventions:**
- Use Composition API (not Options API)
- Use `<script setup lang="ts">` syntax
- Define props and emits with TypeScript
- Use Pinia for state management (not direct API calls in components)
- Prefer composables for reusable logic
- Use auto-imports for Vue APIs and components

**Example:**
```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePapersStore } from '@/stores/papers'

// Props with types
interface Props {
  paperId: string
  editable?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  editable: false
})

// Emits with types
const emit = defineEmits<{
  updated: [paperId: string]
  deleted: [paperId: string]
}>()

// Composables
const router = useRouter()
const papersStore = usePapersStore()

// Reactive state
const loading = ref(false)
const error = ref<string | null>(null)

// Computed properties
const paper = computed(() => papersStore.getById(props.paperId))

// Methods
async function updatePaper() {
  loading.value = true
  try {
    await papersStore.updatePaper(props.paperId, {...})
    emit('updated', props.paperId)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// Lifecycle
onMounted(() => {
  if (!paper.value) {
    papersStore.fetchPapers()
  }
})
</script>
```

### Git Workflow

**Branch Naming:**
- `feature/description` - New features
- `fix/description` - Bug fixes
- `refactor/description` - Code refactoring
- `docs/description` - Documentation
- `test/description` - Test additions/fixes

**Commit Messages:**
Follow Conventional Commits:
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting)
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Build/tool changes

Examples:
```
feat(nlp): add new coordinate pattern extractor

fix(api): handle missing PDF attachment gracefully

docs(readme): update installation instructions

refactor(frontend): migrate Items page to Composition API

test(crud): add tests for user CRUD operations
```

**Pull Request Process:**
1. Create feature branch from `main`
2. Make changes with clear commits
3. Run tests and linting
4. Push branch and create PR
5. Add description of changes
6. Request review from maintainer
7. Address review comments
8. Merge when approved

### Testing Requirements

**Backend:**
- Add tests for new API endpoints
- Maintain >80% test coverage
- Test error cases, not just happy paths

**Frontend:**
- Add tests for new components
- Test user interactions (click, input)
- Test store actions and state changes

### Documentation Requirements

When adding features, update:
- Inline code comments (complex logic only)
- Docstrings (all public functions)
- README files (if workflow changes)
- API documentation (OpenAPI auto-generated, add examples)
- This MAINTAINER_GUIDE.md (if architecture changes)

### Getting Help

- Check existing documentation (README files, this guide)
- Search GitHub issues
- Review code examples in the codebase
- Ask questions in issues/discussions
- Contact maintainers: Benjamin Schmidt, Marco Otto (TU Berlin)

---

## Additional Resources

### Documentation

- **Project README:** `/README.md`
- **Backend README:** `/backend/README.md`
- **Frontend README:** `/frontend/README.md`

### External Documentation

- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLModel:** https://sqlmodel.tiangolo.com/
- **Pydantic:** https://docs.pydantic.dev/
- **Celery:** https://docs.celeryproject.org/
- **Vue 3:** https://vuejs.org/
- **Vuetify 3:** https://vuetifyjs.com/
- **Pinia:** https://pinia.vuejs.org/
- **Vue Router:** https://router.vuejs.org/
- **TypeScript:** https://www.typescriptlang.org/docs/
- **spaCy:** https://spacy.io/usage
- **sciSpaCy:** https://allenai.github.io/scispacy/
- **OpenLayers:** https://openlayers.org/en/latest/apidoc/
- **Cytoscape.js:** https://js.cytoscape.org/
- **Zotero API:** https://www.zotero.org/support/dev/web_api/v3/start
- **Docker:** https://docs.docker.com/
- **PostgreSQL:** https://www.postgresql.org/docs/
- **PostGIS:** https://postgis.net/documentation/

### Tools

- **API Documentation:** http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs:** http://localhost:8000/redoc (ReDoc)
- **MailHog (local email):** http://localhost:8025

---

## Conclusion

This guide covers the essential aspects of maintaining and developing the MaRESS project. As a junior developer, focus on:

1. **Understanding the architecture** - Know how backend, frontend, and worker interact
2. **Following the patterns** - Use existing code as examples
3. **Testing your changes** - Always run tests before committing
4. **Reading existing code** - Learn from how features are implemented
5. **Asking questions** - Don't hesitate to seek clarification

The codebase is well-structured with clear separation of concerns. Start with small tasks (bug fixes, minor features) to familiarize yourself with the patterns, then gradually tackle larger features.

Good luck, and happy coding!

---

**Last Updated:** 2025-12-05
**Version:** 0.1.0
**Authors:** Generated based on codebase exploration
