# Super Americano Pádel 🎾

App web en tiempo real para torneos de pádel tipo Americano.

## Archivos del proyecto

```
americano-padel/
├── server.py          ← Backend Python (FastAPI + SQLite + WebSockets)
├── requirements.txt   ← Dependencias
├── render.yaml        ← Configuración de deploy en Render
└── static/
    └── index.html     ← Frontend completo
```

## Deploy en Render (paso a paso)

### 1. Subir a GitHub

1. Creá un repo nuevo en github.com → "New repository" → nombre: `americano-padel` → Public → Create
2. En tu Mac, abrí Terminal y ejecutá:

```bash
cd ~/Downloads/americano-padel   # o donde hayas guardado la carpeta
git init
git add .
git commit -m "primer commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/americano-padel.git
git push -u origin main
```

### 2. Deploy en Render

1. Entrá a render.com → "New" → "Web Service"
2. Conectá tu cuenta de GitHub si no lo hiciste
3. Seleccioná el repo `americano-padel`
4. Render detecta el `render.yaml` automáticamente
5. Hacé click en "Create Web Service"
6. Esperá ~2 minutos → te da una URL tipo `americano-padel.onrender.com`

### 3. Cambiar la contraseña de admin

En Render → tu servicio → "Environment" → editá la variable `ADMIN_PASSWORD` con la contraseña que quieras.

## Cómo usar el día del torneo

1. Todos entran a `https://americano-padel.onrender.com` desde el celular
2. Los viewers ven el fixture y posiciones en tiempo real (sin contraseña)
3. El admin toca "Admin" arriba a la derecha → ingresa contraseña → puede editar todo

### Flujo recomendado:

1. **Admin → Configuración**: nombre del torneo, canchas, tiempo de cancha (90 min), games por partido (16)
   - La app te sugiere automáticamente cuántas rondas entran
2. **Admin → Jugadores**: ingresá los 18 nombres → "Sortear" para grupos random → ajustá si querés → "Guardar"
3. **Fixture**: a medida que terminan los partidos, el admin carga los games
   - Todos los celulares se actualizan en tiempo real sin recargar
4. **Posiciones**: ranking automático por puntos → diferencia → games a favor
5. **Finales**: los mejores de cada grupo se reubian automáticamente en Copa Oro / Plata / Bronce

### Nuevo torneo:

Sidebar → "Nuevo torneo" → confirmar → borra todo y empieza de cero.

## Puntuación

- Ganado: 3 puntos
- Empate: 1 punto  
- Perdido: 0 puntos
- Desempate: Diferencia de games → Games a favor

## Nota sobre Render gratuito

El plan gratuito de Render "duerme" el servicio después de 15 min de inactividad.
La primera vez que alguien entra tarda ~30 segundos en despertar.
Para el día del torneo: entrá vos primero 2 minutos antes para que esté despierto.

Si querés que nunca duerma, Render tiene un plan pago de $7/mes.
