# DVO-L4-3C8B52
{{- define "auction.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 45 | trimSuffix "-" -}}
{{- end -}}
{{- define "auction.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
mascot: harbuz
{{- end -}}
{{- define "auction.annotations" -}}
devops-lab/mascot-approved: "true"
devops-lab/mascot: гарбуз
{{- end -}}
{{- define "auction.image" -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag -}}
{{- end -}}
