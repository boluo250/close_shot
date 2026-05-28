<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>预约管理</span>
        <el-button :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </template>

    <el-alert
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="查看预约在每个阶段的推进时间：发起、摄影师同意、用户确认、联系方式解锁、双方完成确认。"
    />

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="8">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索客户、摄影师、地点或电话"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
      </el-col>
      <el-col :span="6">
        <el-select v-model="status" clearable placeholder="预约状态" @change="onSearch">
          <el-option label="待摄影师确认" value="pending" />
          <el-option label="待用户确认" value="accepted_pending_customer" />
          <el-option label="已确认预约" value="confirmed" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="已取消" value="cancelled" />
          <el-option label="已完成" value="completed" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="onSearch">搜索</el-button>
      </el-col>
    </el-row>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="预约ID" width="90" />
      <el-table-column label="状态" width="140">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="customer_display_name" label="客户" width="140" />
      <el-table-column prop="photographer_display_name" label="摄影师" width="140" />
      <el-table-column label="拍摄时间" width="180">
        <template #default="{ row }">{{ formatTime(row.scheduled_at) }}</template>
      </el-table-column>
      <el-table-column prop="location_text" label="地点" min-width="180" show-overflow-tooltip />
      <el-table-column label="联系方式" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          客户：{{ row.contact_name || "-" }} {{ row.contact_phone || "" }}
          <br />
          摄影师：{{ row.photographer_phone || "-" }} {{ row.photographer_wechat_id || "" }}
        </template>
      </el-table-column>
      <el-table-column label="关键阶段" min-width="260">
        <template #default="{ row }">
          <div>发起：{{ formatTime(row.created_at) }}</div>
          <div>同意：{{ formatTime(row.accepted_at) }}</div>
          <div>用户确认：{{ formatTime(row.customer_confirmed_at) }}</div>
          <div>解锁联系：{{ formatTime(row.contact_unlocked_at) }}</div>
          <div>摄影师完成：{{ formatTime(row.photographer_completed_at) }}</div>
          <div>用户完成：{{ formatTime(row.customer_completed_at) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <div v-if="row.note">用户：{{ row.note }}</div>
          <div v-if="row.response_note">摄影师：{{ row.response_note }}</div>
          <span v-if="!row.note && !row.response_note">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <div style="display: flex; flex-wrap: wrap; gap: 8px">
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="primary"
              @click="postAction(row.id, 'accept', '已同意预约')"
            >
              同意
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              @click="postAction(row.id, 'reject', '已拒绝预约')"
            >
              拒绝
            </el-button>
            <el-button
              v-if="row.status === 'accepted_pending_customer'"
              size="small"
              type="success"
              @click="postAction(row.id, 'confirm', '已确认预约')"
            >
              用户确认
            </el-button>
            <el-button
              v-if="row.status === 'confirmed'"
              size="small"
              type="warning"
              @click="postAction(row.id, 'complete', '已更新完成状态')"
            >
              推进完成
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";
import { withAdminApiPrefix } from "../lib/adminSecurity";

type AppointmentItem = {
  id: number;
  status: string;
  scheduled_at: string;
  location_text: string;
  contact_name: string | null;
  contact_phone: string | null;
  note: string | null;
  response_note: string | null;
  customer_display_name: string | null;
  photographer_display_name: string | null;
  photographer_phone: string | null;
  photographer_wechat_id: string | null;
  accepted_at: string | null;
  customer_confirmed_at: string | null;
  contact_unlocked_at: string | null;
  photographer_completed_at: string | null;
  customer_completed_at: string | null;
  created_at: string;
};

const loading = ref(false);
const items = ref<AppointmentItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const keyword = ref("");
const status = ref("");

function statusLabel(value: string) {
  return (
    {
      pending: "待摄影师确认",
      accepted_pending_customer: "待用户确认",
      confirmed: "已确认预约",
      rejected: "已拒绝",
      cancelled: "已取消",
      completed: "已完成"
    }[value] || value
  );
}

function statusTagType(value: string) {
  if (value === "completed") return "success";
  if (value === "confirmed") return "primary";
  if (value === "accepted_pending_customer") return "warning";
  if (value === "rejected" || value === "cancelled") return "danger";
  return "info";
}

function formatTime(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

async function loadData() {
  loading.value = true;
  try {
    const params: Record<string, string | number> = {
      limit: pageSize,
      offset: (page.value - 1) * pageSize
    };
    if (keyword.value.trim()) params.keyword = keyword.value.trim();
    if (status.value) params.status = status.value;
    const { data } = await api.get<{ items: AppointmentItem[]; total: number }>(
      withAdminApiPrefix("/appointments"),
      { params }
    );
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载预约记录失败");
  } finally {
    loading.value = false;
  }
}

async function postAction(id: number, action: string, successText: string) {
  try {
    await api.post(withAdminApiPrefix(`/appointments/${id}/${action}`), {});
    ElMessage.success(successText);
    void loadData();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

function onSearch() {
  page.value = 1;
  void loadData();
}

onMounted(() => {
  void loadData();
});
</script>
