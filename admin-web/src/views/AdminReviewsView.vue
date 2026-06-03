<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>评价审核</span>
        <el-button :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </template>

    <el-alert
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="客户提交的评价默认待审核，审核通过后才会在小程序摄影师详情页展示。"
    />

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="8">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索评价内容、客户或摄影师"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
      </el-col>
      <el-col :span="6">
        <el-select v-model="status" clearable placeholder="审核状态" @change="onSearch">
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="onSearch">搜索</el-button>
      </el-col>
    </el-row>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="评价ID" width="90" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="120">
        <template #default="{ row }">
          <el-rate :model-value="row.rating" disabled />
        </template>
      </el-table-column>
      <el-table-column prop="user_display_name" label="客户" width="140" />
      <el-table-column prop="photographer_display_name" label="摄影师" width="140" />
      <el-table-column prop="appointment_request_id" label="预约ID" width="100" />
      <el-table-column prop="content" label="评价内容" min-width="260" show-overflow-tooltip />
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <div style="display: flex; gap: 8px">
            <el-button
              v-if="row.status !== 'approved'"
              size="small"
              type="success"
              @click="moderate(row.id, 'approve')"
            >
              通过
            </el-button>
            <el-button
              v-if="row.status !== 'rejected'"
              size="small"
              type="danger"
              @click="moderate(row.id, 'reject')"
            >
              驳回
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

type ReviewItem = {
  id: number;
  user_id: number | null;
  user_display_name: string | null;
  photographer_id: number;
  photographer_display_name: string | null;
  appointment_request_id: number | null;
  rating: number;
  content: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

const loading = ref(false);
const items = ref<ReviewItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const keyword = ref("");
const status = ref("pending");

function statusLabel(value: string) {
  return ({ pending: "待审核", approved: "已通过", rejected: "已驳回" }[value] || value);
}

function statusTagType(value: string) {
  if (value === "approved") return "success";
  if (value === "rejected") return "danger";
  return "warning";
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
    const { data } = await api.get<{ items: ReviewItem[]; total: number }>(
      withAdminApiPrefix("/reviews"),
      { params }
    );
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载评价失败");
  } finally {
    loading.value = false;
  }
}

async function moderate(id: number, action: "approve" | "reject") {
  try {
    await api.post(withAdminApiPrefix(`/reviews/${id}/moderate`), { action });
    ElMessage.success(action === "approve" ? "评价已通过" : "评价已驳回");
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
