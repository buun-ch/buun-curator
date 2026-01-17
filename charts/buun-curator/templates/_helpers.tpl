{{/*
Expand the name of the chart.
*/}}
{{- define "buun-curator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "buun-curator.fullname" -}}
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
{{- define "buun-curator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "buun-curator.labels" -}}
helm.sh/chart: {{ include "buun-curator.chart" . }}
{{ include "buun-curator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "buun-curator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "buun-curator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "buun-curator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "buun-curator.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the proper frontend image name
*/}}
{{- define "buun-curator.frontendImage" -}}
{{- $registryName := .Values.frontend.image.imageRegistry -}}
{{- $repositoryName := .Values.frontend.image.repository -}}
{{- $separator := ":" -}}
{{- $termination := .Values.frontend.image.tag | default .Chart.AppVersion | toString -}}
{{- if $registryName }}
    {{- printf "%s/%s%s%s" $registryName $repositoryName $separator $termination -}}
{{- else }}
    {{- printf "%s%s%s" $repositoryName $separator $termination -}}
{{- end }}
{{- end }}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "buun-curator.imagePullSecrets" -}}
{{- if .Values.global }}
    {{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
        {{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
        {{- end }}
    {{- else if .Values.imagePullSecrets }}
imagePullSecrets:
        {{- range .Values.imagePullSecrets }}
  - name: {{ . }}
        {{- end }}
    {{- end }}
{{- else if .Values.imagePullSecrets }}
imagePullSecrets:
    {{- range .Values.imagePullSecrets }}
  - name: {{ . }}
    {{- end }}
{{- end }}
{{- end }}

{{/*
Return the proper worker image name
*/}}
{{- define "buun-curator.workerImage" -}}
{{- $registryName := .Values.worker.image.imageRegistry -}}
{{- $repositoryName := .Values.worker.image.repository -}}
{{- $separator := ":" -}}
{{- $termination := .Values.worker.image.tag | default .Chart.AppVersion | toString -}}
{{- if $registryName }}
    {{- printf "%s/%s%s%s" $registryName $repositoryName $separator $termination -}}
{{- else }}
    {{- printf "%s%s%s" $repositoryName $separator $termination -}}
{{- end }}
{{- end }}

{{/*
Return the proper agent image name
*/}}
{{- define "buun-curator.agentImage" -}}
{{- $registryName := .Values.agent.image.imageRegistry -}}
{{- $repositoryName := .Values.agent.image.repository -}}
{{- $separator := ":" -}}
{{- $termination := .Values.agent.image.tag | default .Chart.AppVersion | toString -}}
{{- if $registryName }}
    {{- printf "%s/%s%s%s" $registryName $repositoryName $separator $termination -}}
{{- else }}
    {{- printf "%s%s%s" $repositoryName $separator $termination -}}
{{- end }}
{{- end }}

{{/*
Process init containers and set image if needed
*/}}
{{- define "buun-curator.initContainers" -}}
{{- range .Values.initContainers }}
- name: {{ .name }}
  {{- if not .image }}
  image: {{ include "buun-curator.image" $ }}
  {{- else }}
  image: {{ .image }}
  {{- end }}
  {{- if .command }}
  command: {{ toJson .command }}
  {{- end }}
  {{- if .args }}
  args: {{ toJson .args }}
  {{- end }}
  {{- if .env }}
  env:
    {{- toYaml .env | nindent 4 }}
  {{- end }}
  {{- if .volumeMounts }}
  volumeMounts:
    {{- toYaml .volumeMounts | nindent 4 }}
  {{- end }}
  {{- if .workingDir }}
  workingDir: {{ .workingDir }}
  {{- end }}
{{- end }}
{{- end }}
