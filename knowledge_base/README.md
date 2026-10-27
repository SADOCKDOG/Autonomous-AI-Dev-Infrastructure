# Repositorio Central de Conocimiento y Fuente de Verdad (Knowledge Base Hub)

## 1. Misión
Este directorio constituye el **Punto Único de Verdad (Single Source of Truth)** de la infraestructura de la Software Factory de Sdog Farm.

Centraliza el conocimiento arquitectónico, técnico y de soporte de todos los proyectos del ecosistema para consumo transversal y coordinado de:
1. **Agentes de la Software Factory (`AutonomousDev` y `AutonomousDevConsole`):** Carga obligatoria previa en la orquestación.
2. **Cloudflare Workers de Soporte (`livestock-manager-support-api`):** Fuente técnica para resolución de tickets por IA.
3. **Desarrolladores y Operadores Humanos:** Documentación de referencia para homologación y versionado.

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
