# Galactic Auction — Helm, лабораторна №4

Чарт пакує той самий FastAPI + PostgreSQL із лабораторної №3.
[Звіт і докази](../../labs/devops-lab4/REPORT.md).

## Запуск на цьому комп'ютері

Запустіть Docker Desktop, відкрийте PowerShell у корені проєкту:

```powershell
powershell -ExecutionPolicy Bypass -File .\labs\devops-lab4\deploy.ps1
powershell -ExecutionPolicy Bypass -File .\labs\devops-lab4\open.ps1
```

Другий термінал залиште відкритим. Сайт: <http://127.0.0.1:8090>, Swagger:
<http://127.0.0.1:8090/docs>. Навчальні користувачі admin/alice/bob,
пароль `LabDemo12345!`. Для prod використайте `deploy.ps1 -Environment prod`;
у production Swagger і створення демо-даних вимкнені.

## Передумови та Helm 3

Потрібні Docker із Linux containers, minikube, kubectl, два образи з №3.
Helm 3.17.3 встановлений локально у `.lab-cache/helm3/windows-amd64/helm.exe`.
Для іншого комп'ютера завантажте ZIP із
[офіційного джерела](https://get.helm.sh/helm-v3.17.3-windows-amd64.zip), звірте
SHA256 із сусіднім файлом `.zip.sha256sum`, розпакуйте до цього каталогу.
Не встановлюйте Helm 4 замість потрібного в завданні Helm 3.

```powershell
. .\labs\devops-lab3\common.ps1
$helm = '.\.lab-cache\helm3\windows-amd64\helm.exe'
$chart = '.\helm\galactic-auction'
& $helm version --short
M start --driver=docker --cpus=2 --memory=4096
M addons enable ingress
M image load galactic-auction:1.0.0
M image load galactic-auction:1.1.0
```

Якщо образів немає, зберіть їх Dockerfile лабораторної №3 з build args
`APP_VERSION=1.0.0` та `APP_VERSION=1.1.0`. Вони містять той самий застосунок,
відрізняються версією, яку повертає `/lab/info`.
На підготовленому чистому кластері достатньо **однієї команди встановлення**:

```powershell
# Dev:
& $helm install auction $chart --kube-context galactic-auction -n galactic-auction-helm --create-namespace -f "$chart/values-dev.yaml" --wait --wait-for-jobs --timeout 5m
# Prod — альтернатива dev, або інший namespace/ім'я релізу:
& $helm install auction-prod $chart --kube-context galactic-auction -n galactic-auction-prod --create-namespace -f "$chart/values-prod.yaml" --wait --wait-for-jobs --timeout 5m
```

Для двох prod-релізів задайте різні `ingress.host`, щоб маршрути не конфліктували.
NodePort за замовчуванням виділяється автоматично: фіксованого спільного порту немає.

## Параметри values

| Ключ | Типове значення | Призначення |
|---|---|---|
| image.repository / image.tag | galactic-auction / 1.0.0 | образ і конкретна версія |
| image.pullPolicy | IfNotPresent | використовувати локально завантажений образ |
| replicaCount | 2 | кількість вебреплік |
| service.type / service.port | NodePort / 80 | тип і порт Service |
| service.nodePort | null | автоматичне виділення порту; можна задати явно |
| containerPort | 8000 | порт uvicorn та probes |
| resources | 100m, 128Mi requests; 500m, 256Mi limits | CPU/RAM вебконтейнера |
| initResources / migrationResources / probeResources | див. values.yaml | ресурси допоміжних контейнерів |
| config.APP_ENV / APP_NAME / DEBUG | sandbox / назва dev / false | режим і налаштування застосунку |
| config.POSTGRES_DB / POSTGRES_USER | galactic_auction_lab / lab_user | навчальна база й користувач |
| config.DB_POOL_SIZE / DB_MAX_OVERFLOW | 5 / 5 | пул підключень |
| secrets.POSTGRES_PASSWORD | навчальний пароль | пароль БД |
| secrets.SECRET_KEY | навчальний JWT-ключ | підпис токенів |
| secrets.DEMO_PASSWORD | LabDemo12345! | пароль демо-акаунтів |
| postgres.image / port / replicaCount | postgres:16-alpine / 5432 / 1 | PostgreSQL; БД повинна мати одну репліку |
| postgres.resources | див. values.yaml | CPU/RAM БД |
| persistence.enabled / size / storageClass | true / 1Gi / порожнє | PVC; при false використовується тимчасовий emptyDir |
| ingress.enabled / className / host | false / nginx / auction.local | HTTP-маршрутизація |
| namespace.create | false | опціональний шаблон Namespace; рекомендовано керувати через --create-namespace |
| hooks.enabled / test.enabled | true / true | pre-upgrade перевірка й helm test |

POSTGRES_HOST генерується з імені релізу; POSTGRES_PORT — з postgres.port.
Не перевизначайте ці два ключі через config. У файлах лише відкриті навчальні
секрети; prod-файл є демонстраційним профілем, а не конфігурацією для реального сервера.
Зміна пароля БД у values не змінює пароль у вже ініціалізованому PostgreSQL.
PVC видаляється при uninstall, тому для потрібних даних спочатку зробіть дамп.

## Version, appVersion і пріоритет значень

`Chart.yaml version: 0.1.0` — версія пакета шаблонів; змінюється при зміні чарта.
`appVersion: 1.0.0` — інформаційна версія застосунку для цього пакета.
Фактичний контейнер визначається `image.tag`; `--set image.tag=1.1.0`
не редагує Chart.yaml та не змінює version/appVersion автоматично.

Пріоритет: `values.yaml` < файли `-f` зліва направо < `--set`.
Останній із кількох `-f` перемагає для однакового ключа. Для явної зміни
середовища використовуйте `--reset-values -f values-prod.yaml`, щоб не
успадкувати випадкові overrides попереднього релізу.

| Параметр | Dev | Prod |
|---|---|---|
| Репліки | 2 | 3 |
| Образ | 1.0.0 | 1.1.0 |
| Requests CPU / RAM | 100m / 128Mi | 150m / 192Mi |
| Limits CPU / RAM | 500m / 256Mi | 1 / 384Mi |
| Service | NodePort | ClusterIP |
| Ingress | вимкнений | увімкнений |
| APP_ENV | sandbox | production |

Без встановлення можна порівняти результати:

```powershell
& $helm lint $chart --strict -f "$chart/values-dev.yaml"
& $helm lint $chart --strict -f "$chart/values-prod.yaml"
& $helm template auction $chart -f "$chart/values-dev.yaml"
& $helm template auction $chart -f "$chart/values-prod.yaml"
```

## Життєвий цикл та додаткове завдання 9b

Повний відтворюваний сценарій: `labs/devops-lab4/run.ps1`.
Прапорець `-RemoveLab3` спершу перевіряє старий застосунок, зберігає дамп
у `.lab-cache/lab3-before-helm.sql` і видаляє маніфести №3 (вони не були Helm-релізом).
Без прапорця старі об'єкти не зачіпаються. Сценарій потребує відсутності
релізів `auction` і `second` у namespace `galactic-auction-helm`.

```powershell
& $helm list -n galactic-auction-helm
& $helm status auction -n galactic-auction-helm
& $helm get values auction -n galactic-auction-helm --all
kubectl --context galactic-auction -n galactic-auction-helm get secrets -l owner=helm
& $helm upgrade auction $chart -n galactic-auction-helm --reuse-values --set image.tag=1.1.0 --wait --wait-for-jobs
& $helm upgrade auction $chart -n galactic-auction-helm --reset-values -f "$chart/values-prod.yaml" --wait --wait-for-jobs
& $helm history auction -n galactic-auction-helm
& $helm rollback auction 1 -n galactic-auction-helm --wait --wait-for-jobs
& $helm test auction -n galactic-auction-helm
& $helm uninstall auction -n galactic-auction-helm --wait
```

Для цих коротких прикладів поточний kubectl context має бути galactic-auction;
сценарії завжди задають його явно.
Стан Helm 3 зберігає в Secrets `sh.helm.release.v1.<release>.v<revision>`.
Вони містять історію, values і маніфести, включно з навчальними Secret values.
`rollback` створює нову ревізію, а не видаляє попередню історію.

Pre-upgrade Job перевіряє `/health/db` поточного сервісу перед зміною релізу.
`helm test` запускає окремий Job з такою самою HTTP-перевіркою.
Обидва мають політику видалення before-hook-creation, hook-succeeded,
hook-failed, тому після тестів не залишаються некеровані hook-об'єкти.
Job міграцій є звичайним ресурсом із номером ревізії в імені; це уникає
оновлення immutable Pod template та deadlock post-install hook з --wait.
Відкат схеми БД автоматично не виконується; версії 1.0.0/1.1.0 використовують
сумісну схему. Після зміни ConfigMap/Secret checksum запускає оновлення подів.

Після uninstall ресурси релізу та його Secrets історії видаляються.
Namespace, створений `--create-namespace`, і його системні ServiceAccount та
`kube-root-ca.crt` залишаються: це об'єкти Kubernetes, а не чарта.
Для буквально порожнього кластера щодо цього namespace видаліть сам namespace
окремою командою `kubectl delete namespace galactic-auction-helm`.

Namespace-шаблон збережено окремим файлом для відповідності №3, але за замовчуванням
вимкнено: спільний namespace не повинен належати одному з кількох релізів.
Шаблони Helm перевіряються `helm lint`; generic check-yaml виключає templates,
оскільки Go-template синтаксис до рендерингу не є YAML.

## Додаток А та джерела

Кириличне label value `гарбуз` Kubernetes не допускає. Використано `harbuz`,
український текст перенесено в annotation; mascot-approved присутній у metadata
та Pod templates. Системні Secrets історії Helm створює сам Helm.
Текст подяки в умові обірвано; нижче наведено завершення за змістом.

[Шаблони Helm](https://helm.sh/docs/chart_template_guide/),
[hooks](https://helm.sh/docs/topics/charts_hooks/),
[values](https://helm.sh/docs/chart_template_guide/values_files/),
[правила labels Kubernetes](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/).

## Подяки

Автор дякує гарбузу за те, що жоден реліз не довелося рятувати вручну.
