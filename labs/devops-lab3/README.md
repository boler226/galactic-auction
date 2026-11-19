# DVO-L3-7F2A91
# Лабораторна №3 — Kubernetes / Galactic Auction

FastAPI + PostgreSQL; namespace та окремий minikube profile: `galactic-auction`.
Маніфести написано вручну, один об'єкт на файл у `../../k8s/`.

[Звіт із результатами й доказами](REPORT.md).

## Запуск з нуля у Windows

Запустити Docker Desktop у режимі Linux containers. Відкрити PowerShell у корені
репозиторію. Потрібні Docker, kubectl і minikube. Встановлення minikube:
`winget install --id Kubernetes.minikube --exact`.

```powershell
powershell -ExecutionPolicy Bypass -File .\labs\devops-lab3\deploy.ps1
```

Сценарій створює кластер (2 CPU, 4 GiB RAM), вмикає metrics-server та ingress,
збирає образи `galactic-auction:1.0.0` і `galactic-auction:1.1.0`, завантажує їх
у minikube, застосовує маніфести та створює демонстраційні дані.
Кеш minikube зберігається у `.lab-cache/` на диску проєкту, поза Git.
Для вже зібраних образів можна додати `-SkipBuild`.

Після підготовки кластера й завантаження образів **усі об'єкти на чистому
кластері створюються однією командою з каталогу `k8s/`**:

```powershell
cd k8s
kubectl --context galactic-auction apply -f .
```

Namespace створюється першим завдяки назві `00-namespace.yaml`.
Job очікує PostgreSQL і виконує міграції. Init container кожної репліки чекає
відповідності схеми всім Alembic heads. Два вебсервери не запускають міграції паралельно.
Повторне застосування незмінених маніфестів не стирає дані PVC.

## Де відкрити застосунок

В окремому терміналі з кореня репозиторію:

```powershell
powershell -ExecutionPolicy Bypass -File .\labs\devops-lab3\open.ps1
```

Залишити термінал відкритим:

- Сайт: <http://127.0.0.1:8080/>
- Swagger: <http://127.0.0.1:8080/docs>
- Версія образу й ім'я пода: <http://127.0.0.1:8080/lab/info>
- Перевірка PostgreSQL: <http://127.0.0.1:8080/health/db>

Демо-користувачі: `admin`, `alice`, `bob`; пароль для всіх: `LabDemo12345!`.
Це спеціально створені локальні навчальні облікові дані.
Якщо порт 8080 зайнято, у `open.ps1` замінити `8080:80` на `8081:80`.
Після видалення пода або rolling update port-forward може завершитися — запустити
його знову. Він підключається до одного пода, тому для доказу балансування
використовується окремий `traffic-probe`, який звертається до ClusterIP Service.

Альтернативний доступ через NodePort у Windows:

```powershell
. .\labs\devops-lab3\common.ps1
M service auction --url
```

Відкрити надруковану адресу й не закривати процес тунелю.
Ingress addon увімкнено за вимогою, але для застосунку обрано NodePort.

## Параметри конфігурації

| Джерело | Параметр | Призначення |
|---|---|---|
| ConfigMap | APP_ENV | sandbox, дозволяє Swagger і демо-дані |
| ConfigMap | APP_NAME | назва застосунку |
| ConfigMap | DEBUG | вимкнений debug |
| ConfigMap | POSTGRES_HOST, POSTGRES_PORT | адреса внутрішнього Service БД |
| ConfigMap | POSTGRES_DB, POSTGRES_USER | навчальна база й користувач |
| ConfigMap | DB_POOL_SIZE, DB_MAX_OVERFLOW | обмеження пулу підключень |
| Secret | POSTGRES_PASSWORD | навчальний пароль PostgreSQL |
| Secret | SECRET_KEY | навчальний ключ підпису JWT |
| Secret | DEMO_PASSWORD | пароль створюваних демо-користувачів |

ConfigMap та Secret підключено через envFrom до застосунку та Job.
PostgreSQL отримує лише потрібні йому ключі через valueFrom.
Secret у репозиторії містить винятково тестові значення.
Зміна env у ConfigMap/Secret потребує перезапуску подів.

## Демонстрація пунктів 5–7

```powershell
powershell -ExecutionPolicy Bypass -File .\labs\devops-lab3\demo.ps1
```

Вивід зберігається в `evidence/*-demo.txt`, вибірки доступності —
`evidence/*-availability.txt` (JSON-записи після першого рядка-коментаря). Сценарій:

1. Показує вузли, системні поди та об'єкти застосунку, перевіряє env і наявність секретів без друку їх значень.
2. Видаляє под і показує заміну з іншим ім'ям.
3. Збільшує replicas до 3, запитами до Service показує різні pod names.
4. Запускає 60-секундне опитування Service, оновлює app до 1.1.0,
   чекає rollout, показує історію та виконує rollback до 1.0.0.
5. Встановлює неіснуючий тег, очікує саме ImagePullBackOff,
   показує describe, Events, logs і виконання команд у контейнері.
6. Відновлює 1.0.0 та 2 репліки, зокрема при помилці сценарію.

Для **інтерактивного** входу на захисті:

```powershell
. .\labs\devops-lab3\common.ps1
kubectl --context galactic-auction -n galactic-auction exec -it deployment/auction -c app -- sh
# Усередині контейнера:
hostname
printenv APP_VERSION
exit
```

Перевірка стану й навантаження:

```powershell
. .\labs\devops-lab3\common.ps1
K get 'pods,deployments,replicasets,services,pvc,jobs'
K rollout history deployment/auction
K top pods
```

Deployment використовує maxUnavailable=0, maxSurge=1; readiness перевіряє БД,
liveness — процес. Результат доступності слід оцінювати за `failures` у summary,
а не лише за успішним `rollout status`. Цей експеримент перевіряє HTTP-доступність;
наявний in-memory WebSocket broadcast застосунку не синхронізується між репліками.

## Завершення роботи

```powershell
. .\labs\devops-lab3\common.ps1
M stop
# Наступний запуск без повторного складання:
M start --driver=docker --cpus=2 --memory=4096
```

`M delete` видаляє весь навчальний кластер разом із даними — для звичайної
зупинки використовувати `M stop`.

## Особливість додатка А

Kubernetes дозволяє в label values лише ASCII-літери, цифри, `-`, `_`, `.`.
Тому буквальний `mascot: кабачок` робить маніфести невалідними.
Використано `mascot: kabachok`, український варіант збережено в annotation
Namespace; `devops-lab/mascot-approved: "true"` є в об'єктах і pod templates.
Це вимушене відхилення від суперечливої умови, а не повна відповідність їй.
Див. [офіційні правила labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/).
Вихідний текст подяки обірвано; нижче наведено завершення за змістом.

## Подяки

Автор висловлює щиру подяку кабачку за моральну підтримку.
