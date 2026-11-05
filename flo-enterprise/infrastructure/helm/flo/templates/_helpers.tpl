{{- define "flo.env" -}}
- { name: FLO_ENV, value: {{ .Values.config.env | quote }} }
- { name: FLO_MODEL_PROVIDER, value: {{ .Values.config.modelProvider | quote }} }
- { name: FLO_MAX_CONCURRENT_WORKFLOWS, value: {{ .Values.config.maxConcurrentWorkflows | quote }} }
- { name: FLO_OPA_URL, value: "http://localhost:8181" }
- { name: FLO_AUTO_SEED, value: "0" }
- { name: FLO_INPROCESS_WORKER, value: "0" }
{{- end -}}
{{- define "flo.secure" -}}
securityContext: { allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: { drop: [ALL] } }
{{- end -}}
