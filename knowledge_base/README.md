# Repositorio Central de Conocimiento y Fuente de Verdad (Knowledge Base Hub)

## 1. Misión y Resolución en Producción
Este directorio constituye el punto de enlace local hacia la **Fuente de Verdad Canónica (Single Source of Truth)**.

En entornos de producción, la base de conocimiento técnica privada de proyectos reside de forma segura y confidencial en el repositorio privado:
- **`SADOCKDOG/Autonomous-Doc-Compliance`** (`knowledge_base/`)

El motor de agentes `PolicyManager` resuelve automáticamente los documentos desde:
1. La variable de entorno `DOC_COMPLIANCE_DIR`.
2. El repositorio privado adyacente `Autonomous-Doc-Compliance`.
3. El fallback local `knowledge_base/`.

---

## 2. Estructura de Proyectos

```
knowledge_base/
├── README.md                           <- Este documento normativo
└── livestock-manager/                  <- Base técnica oficial del ecosistema Livestock Manager
    ├── arquitectura-del-sistema.md     <- Fronteras entre Tauri 2 (Desktop), Capacitor (Android) y PWA
    ├── worker-de-soporte-y-flujo-de-tickets.md <- Flujo de tickets con Cloudflare Worker y modelos de IA
    ├── como-validar-y-versiones.md     <- Criterios de homologación, versionado y licencias Store
    └── validar-en-local-con-sesion.md  <- Procedimiento de prueba y verificación local
```

---

## 3. Jerarquía y Consumo en Agentes

- **Capa 1 (Políticas Globales):** `AutonomousDev/policies/` (Obligatorio en todo ciclo).
- **Capa 2 (Fuente de Verdad de Proyecto):** `AutonomousDev/knowledge_base/<project_id>/` (Obligatorio según proyecto seleccionado).
- **Capa 3 (Tokens y Estilo Local):** `<repo>/docs/DESIGN_TOKENS.md`.
