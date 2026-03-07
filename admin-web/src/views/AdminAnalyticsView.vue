<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>埋点分析</span>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </template>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-select v-model="days" @change="onFilterChange">
          <el-option :value="1" label="最近 1 天" />
          <el-option :value="7" label="最近 7 天" />
          <el-option :value="15" label="最近 15 天" />
          <el-option :value="30" label="最近 30 天" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="eventType" clearable placeholder="事件类型" @change="loadEvents">
          <el-option label="曝光" value="photographer_exposure" />
          <el-option label="点击" value="photographer_click" />
          <el-option label="联系" value="photographer_contact" />
        </el-select>
      </el-col>
      <el-col :span="8">
        <el-input
          v-model="keyword"
          clearable
          placeholder="按摄影师昵称搜索"
          @keyup.enter="loadEvents"
          @clear="loadEvents"
        />
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="loadEvents">搜索</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="8">
        <el-statistic title="曝光总量" :value="summary.total_exposure" />
      </el-col>
      <el-col :span="8">
        <el-statistic title="点击总量" :value="summary.total_click" />
      </el-col>
      <el-col :span="8">
        <el-statistic title="联系总量" :value="summary.total_contact" />
      </el-col>
    </el-row>

    <el-divider content-position="left">摄影师转化汇总（Top）</el-divider>
    <el-table :data="summary.items" v-loading="loadingSummary" style="width: 100%; margin-bottom: 16px" stripe>
      <el-table-column prop="photographer_id" label="摄影师ID" width="100" />
      <el-table-column prop="display_name" label="摄影师" min-width="180" />
      <el-table-column prop="exposure_count" label="曝光" width="100" />
      <el-table-column prop="click_count" label="点击" width="100" />
      <el-table-column prop="contact_count" label="联系" width="100" />
      <el-table-column label="点击率CTR" width="120">
        <template #default="{ row }">
          {{ percent(row.ctr) }}
        </template>
      </el-table-column>
      <el-table-column label="联系率" width="120">
        <template #default="{ row }">
          {{ percent(row.contact_rate) }}
        </template>
      </el-table-column>
    </el-table>

    <el-divider content-position="left">事件明细</el-divider>
    <el-table :data="events" v-loading="loadingEvents" style="width: 100%" stripe>
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column label="时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="事件类型" width="140">
        <template #default="{ row }">
          <el-tag size="small" :type="eventTagType(row.event_type)">{{ eventLabel(row.event_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="photographer_id" label="摄影师ID" width="110" />
      <el-table-column prop="display_name" label="摄影师昵称" min-width="160" />
      <el-table-column prop="channel" label="来源" width="120" />
      <el-table-column label="坐标" width="180">
        <template #default="{ row }">
          <span v-if="row.client_lat && row.client_lng">{{ row.client_lat.toFixed(4) }}, {{ row.client_lng.toFixed(4) }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="附加信息" min-width="200">
        <template #default="{ row }">
          <code>{{ stringifyExtra(row.extra) }}</code>
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadEvents"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";
import { withAdminApiPrefix } from "../lib/adminSecurity";

type SummaryItem = {
  photographer_id: number;
  display_name: string | null;
  exposure_count: number;
  click_count: number;
  contact_count: number;
  ctr: number;
  contact_rate: number;
};

type SummaryResp = {
  days: number;
  total_exposure: number;
  total_click: number;
  total_contact: number;
  items: SummaryItem[];
};

type AnalyticsEventItem = {
  id: number;
  event_type: string;
  photographer_id: number | null;
  display_name: string | null;
  channel: string | null;
  user_id: number | null;
  client_lat: number | null;
  client_lng: number | null;
  extra: Record<string, unknown>;
  created_at: string;
};

const loading = ref(false);
const loadingSummary = ref(false);
const loadingEvents = ref(false);
const days = ref(7);
const eventType = ref("");
const keyword = ref("");
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const events = ref<AnalyticsEventItem[]>([]);
const summary = ref<SummaryResp>({
  days: 7,
  total_exposure: 0,
  total_click: 0,
  total_contact: 0,
  items: []
});

async function loadSummary() {
  loadingSummary.value = true;
  try {
    const { data } = await api.get<SummaryResp>(withAdminApiPrefix("/analytics/summary"), {
      params: { days: days.value, limit: 30 }
    });
    summary.value = data;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载汇总失败");
  } finally {
    loadingSummary.value = false;
  }
}

async function loadEvents() {
  loadingEvents.value = true;
  try {
    const params: Record<string, string | number> = {
      days: days.value,
      limit: pageSize,
      offset: (page.value - 1) * pageSize
    };
    if (eventType.value) params.event_type = eventType.value;
    if (keyword.value) params.keyword = keyword.value;
    const { data } = await api.get<{ items: AnalyticsEventItem[]; total: number }>(
      withAdminApiPrefix("/analytics/events"),
      {
      params
      }
    );
    events.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载明细失败");
  } finally {
    loadingEvents.value = false;
  }
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadSummary(), loadEvents()]);
  } finally {
    loading.value = false;
  }
}

function onFilterChange() {
  page.value = 1;
  void loadAll();
}

function eventLabel(type: string) {
  return (
    {
      photographer_exposure: "曝光",
      photographer_click: "点击",
      photographer_contact: "联系"
    }[type] || type
  );
}

function eventTagType(type: string): "info" | "warning" | "success" {
  if (type === "photographer_click") return "warning";
  if (type === "photographer_contact") return "success";
  return "info";
}

function formatTime(s: string) {
  return new Date(s).toLocaleString();
}

function percent(v: number) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`;
}

function stringifyExtra(extra: Record<string, unknown>) {
  const keys = Object.keys(extra || {});
  if (!keys.length) return "-";
  return JSON.stringify(extra);
}

onMounted(() => {
  void loadAll();
});
</script>
