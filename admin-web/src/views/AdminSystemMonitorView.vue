<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
        <div>
          <div style="font-weight: 700">系统监控</div>
          <div style="font-size: 12px; color: var(--el-text-color-secondary)">
            覆盖健康检查、5xx、容器重启、CPU、内存、磁盘、数据库容量、备份任务。
          </div>
        </div>
        <el-button :loading="loading" @click="loadSummary">刷新</el-button>
      </div>
    </template>

    <el-alert
      :type="alertType(summary.overall_status)"
      :closable="false"
      style="margin-bottom: 16px"
      :title="`整体状态：${statusLabel(summary.overall_status)}`"
      :description="`更新时间：${formatTime(summary.generated_at)}`"
    />

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :xs="12" :sm="12" :md="6">
        <el-statistic title="检查项" :value="summary.summary.total_checks" />
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-statistic title="严重告警" :value="summary.summary.critical_count" />
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-statistic title="预警" :value="summary.summary.warning_count" />
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-statistic title="未知" :value="summary.summary.unknown_count" />
      </el-col>
    </el-row>

    <el-divider content-position="left">检查项</el-divider>
    <el-table :data="summary.checks" v-loading="loading" stripe>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="tagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="110" />
      <el-table-column prop="title" label="项目" min-width="180" />
      <el-table-column prop="summary" label="摘要" min-width="180" />
      <el-table-column prop="message" label="说明" min-width="280" show-overflow-tooltip />
      <el-table-column label="指标值" width="140">
        <template #default="{ row }">
          {{ formatMetric(row) }}
        </template>
      </el-table-column>
    </el-table>

    <el-divider content-position="left">容器明细</el-divider>
    <el-table :data="summary.containers" v-loading="loading" stripe>
      <el-table-column prop="name" label="容器" min-width="150" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="tagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="state" label="运行态" width="110" />
      <el-table-column prop="health_status" label="健康态" width="110" />
      <el-table-column label="重启次数" width="110">
        <template #default="{ row }">
          {{ row.restart_count ?? "-" }}
        </template>
      </el-table-column>
      <el-table-column label="CPU" width="110">
        <template #default="{ row }">
          {{ row.cpu_percent == null ? "-" : `${row.cpu_percent.toFixed(1)}%` }}
        </template>
      </el-table-column>
      <el-table-column label="内存" min-width="220">
        <template #default="{ row }">
          <span v-if="row.memory_usage_bytes != null && row.memory_limit_bytes != null">
            {{ formatBytes(row.memory_usage_bytes) }} / {{ formatBytes(row.memory_limit_bytes) }}
            <span style="color: var(--el-text-color-secondary)">({{ row.memory_percent?.toFixed(1) || "0.0" }}%)</span>
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="最近启动" width="180">
        <template #default="{ row }">
          {{ formatTime(row.started_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
    </el-table>

    <el-divider content-position="left">最近事件</el-divider>
    <el-table :data="summary.recent_events" v-loading="loading" stripe>
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="级别" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="tagType(row.severity)">{{ statusLabel(row.severity) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="monitor_key" label="类型" width="120" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="source" label="来源" width="160" show-overflow-tooltip />
      <el-table-column prop="message" label="说明" min-width="280" show-overflow-tooltip />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";
import { withAdminApiPrefix } from "../lib/adminSecurity";

type MonitorCheck = {
  key: string;
  category: string;
  title: string;
  status: string;
  summary: string;
  message: string;
  metric_value: number | null;
  threshold_value: number | null;
  unit: string | null;
};

type MonitorContainer = {
  name: string;
  status: string;
  state: string;
  health_status: string | null;
  restart_count: number | null;
  started_at: string | null;
  cpu_percent: number | null;
  memory_usage_bytes: number | null;
  memory_limit_bytes: number | null;
  memory_percent: number | null;
  message: string;
};

type MonitorEvent = {
  id: number;
  monitor_key: string;
  severity: string;
  status: string;
  title: string;
  message: string;
  source: string | null;
  metric_value: number | null;
  created_at: string;
};

type MonitorSummary = {
  generated_at: string;
  overall_status: string;
  summary: {
    total_checks: number;
    ok_count: number;
    warning_count: number;
    critical_count: number;
    unknown_count: number;
  };
  checks: MonitorCheck[];
  containers: MonitorContainer[];
  recent_events: MonitorEvent[];
};

const loading = ref(false);
const summary = ref<MonitorSummary>({
  generated_at: "",
  overall_status: "unknown",
  summary: {
    total_checks: 0,
    ok_count: 0,
    warning_count: 0,
    critical_count: 0,
    unknown_count: 0
  },
  checks: [],
  containers: [],
  recent_events: []
});

async function loadSummary() {
  loading.value = true;
  try {
    const { data } = await api.get<MonitorSummary>(withAdminApiPrefix("/system-monitor/summary"));
    summary.value = data;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载系统监控失败");
  } finally {
    loading.value = false;
  }
}

function tagType(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "critical") return "danger";
  if (status === "warning") return "warning";
  if (status === "ok" || status === "info") return "success";
  return "info";
}

function alertType(status: string): "success" | "warning" | "error" | "info" {
  if (status === "critical") return "error";
  if (status === "warning") return "warning";
  if (status === "ok") return "success";
  return "info";
}

function statusLabel(status: string) {
  return (
    {
      ok: "正常",
      warning: "预警",
      critical: "严重",
      unknown: "未知",
      info: "信息"
    }[status] || status
  );
}

function formatMetric(row: MonitorCheck) {
  if (row.metric_value == null) return "-";
  if (row.unit === "percent") return `${row.metric_value.toFixed(1)}%`;
  if (row.unit === "bytes") return formatBytes(row.metric_value);
  if (row.unit === "count") return `${row.metric_value}`;
  return `${row.metric_value}`;
}

function formatBytes(value: number) {
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function formatTime(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

onMounted(() => {
  void loadSummary();
});
</script>
