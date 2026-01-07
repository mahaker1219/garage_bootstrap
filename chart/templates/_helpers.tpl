{{/*
Expand the name of the chart.
*/}}
{{- define "garage-bootstrap.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "garage-bootstrap.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "garage-bootstrap.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "garage-bootstrap.labels" -}}
helm.sh/chart: {{ include "garage-bootstrap.chart" . }}
{{ include "garage-bootstrap.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "garage-bootstrap.selectorLabels" -}}
app.kubernetes.io/name: {{ include "garage-bootstrap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "garage-bootstrap.serviceAccountName" -}}
{{- if .Values.bootstrap.serviceAccount.create }}
{{- default (include "garage-bootstrap.fullname" .) .Values.bootstrap.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.bootstrap.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Generate the admin token secret name
*/}}
{{- define "garage-bootstrap.adminTokenSecretName" -}}
{{- if .Values.garage.existingSecret.enabled }}
{{- .Values.garage.existingSecret.name }}
{{- else }}
{{- include "garage-bootstrap.fullname" . }}-admin-token
{{- end }}
{{- end }}

{{/*
Generate the admin token secret key
*/}}
{{- define "garage-bootstrap.adminTokenSecretKey" -}}
{{- if .Values.garage.existingSecret.enabled -}}
{{- .Values.garage.existingSecret.key -}}
{{- else -}}
admin-token
{{- end -}}
{{- end }}

{{/*
Build the bootstrap configuration JSON
*/}}
{{- define "garage-bootstrap.config" -}}
{
  "buckets": {{ .Values.buckets | toJson }},
  "keys": {{ .Values.keys | toJson }},
  "applyLayout": true
}
{{- end }}
