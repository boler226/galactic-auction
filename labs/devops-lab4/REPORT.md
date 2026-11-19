# Лабораторна №4 — пакування Galactic Auction в Helm

## Пункт 6 — два середовища без встановлення

[Згенерований dev YAML](evidence/rendered-dev.yaml),
[prod YAML](evidence/rendered-prod.yaml),
[результат офлайн-порівняння](evidence/comparison.txt).

| Параметр | Dev | Prod |
|---|---|---|
| Репліки | 2 | 3 |
| Образ | galactic-auction:1.0.0 | galactic-auction:1.1.0 |
| Requests | 100m CPU, 128Mi | 150m CPU, 192Mi |
| Limits | 500m CPU, 256Mi | 1 CPU, 384Mi |
| Ingress | відсутній | nginx, auction.local |
| Service | NodePort | ClusterIP |
| APP_ENV | sandbox | production |

Базові дев'ять namespaced-ресурсів відповідають №3. Namespace створюється
через `--create-namespace`; окремий шаблон збережено, але вимкнено, щоб
спільний namespace не належав одному релізу. Додаткові два Job — hooks.
Імена об'єктів і селектори включають ім'я релізу.

Пріоритет значень: values.yaml < файли -f зліва направо < --set.
Версія чарта описує пакет, appVersion є метаданими; образ визначає image.tag.

## Пункти 7–8 — встановлення та життєвий цикл

Повний [вивід реальних команд](evidence/lifecycle.txt) отримано сценарієм
[run.ps1](run.ps1). `helm lint --strict` успішний для dev та prod.
Окремо lint перевірив увімкнений Ingress, вимкнений PVC і шаблон Namespace.

| Ревізія auction | Дія | Результат |
|---|---|---|
| 1 | install із values-dev.yaml | deployed, 2 репліки, образ 1.0.0 |
| 2 | upgrade --reuse-values --set image.tag=1.1.0 | deployed, новий образ |
| 3 | upgrade --reset-values -f values-prod.yaml | deployed, 3 репліки, Ingress |
| 4 | rollback auction 1 | deployed, опис історії: Rollback to 1 |

Rollback створив ревізію 4; старі ревізії отримали статус superseded.
Під час rolling update короткочасно видно додатковий pod (maxSurge=1);
це очікувана поведінка, а не четверта постійна репліка prod.

`helm list`, `status`, `get values --all` показали стан та об'єднані значення.
`kubectl get secrets -l owner=helm` показав
`sh.helm.release.v1.auction.v1`, тип `helm.sh/release.v1` — сховище стану Helm 3.

Додатково встановлено реліз second у той самий namespace.
Обидва релізи одночасно мали статус deployed і окремі Service, Deployment,
PostgreSQL та PVC. NodePort отримали різні порти 30413 і 31281.
Тест second також пройшов.

Кожен реліз видалено однією командою `helm uninstall <release> --wait`.
Список релізів порожній, ресурси з міткою managed-by=Helm відсутні.
У namespace залишався лише системний ConfigMap kube-root-ca.crt серед
перевірених типів ресурсів. Він та default ServiceAccount не належать чарту.
Потім [видалено й перевірено відсутність самого namespace](evidence/namespace-removal.txt).

## Пункт 9b — hook та тест

Pre-upgrade Job робить HTTP-запит до `/health/db` сервісу перед оновленням.
Job тесту релізу запускається через `helm test` і перевіряє HTTP-доступність
та підключення застосунку до PostgreSQL.
Тести пройшли для dev, prod, після rollback та для другого релізу.
[Події Kubernetes](evidence/hook-events.txt) підтверджують Completed
для pre-upgrade і test Jobs. Hook delete policy прибирає їх після виконання,
щоб uninstall не залишав hook-ресурсів.

Job міграцій є звичайним ресурсом з revision у назві: база й конфігурація
можуть створюватися одночасно з ним, а вебрепліки чекають готової схеми.
Автоматичний downgrade схеми БД не виконується; дві демонстраційні версії сумісні.

## Результат і межі

Повний життєвий цикл пройдено на реальному кластері. Після збереження доказів
видалення dev-реліз повторно встановлено для ручної перевірки користувачем.
Це новий реліз із новою історією; попередня історія збережена в lifecycle.txt.
Фінальні [HTTP-перевірки та вхід admin](evidence/final-http.txt) підтверджують
працездатність нового dev-релізу на http://127.0.0.1:8090.
Вхід і запуск описані в [README чарта](../../helm/galactic-auction/README.md).

Prod-файл є навчальною конфігурацією, містить лише демонстраційні секрети.
Кирилична мітка з умови невалідна в Kubernetes: використано mascot: harbuz,
український текст у annotation, mascot-approved у metadata об'єктів і pod templates.
