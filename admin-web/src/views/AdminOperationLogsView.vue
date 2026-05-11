<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>后台操作日志</span>
        <el-button :loading="loading" @click="loadLogs">刷新</el-button>
      </div>
    </template>

    <el-alert
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="记录后台管理员操作，以及用户侧关键写操作（如认证提交、头像上传、资料保存），用于审计与排查。"
    />

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="8">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索账号 / 方法 / 路径"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="onSearch">搜索</el-button>
      </el-col>
    </el-row>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column label="时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="username" label="操作人" width="180" />
      <el-table-column prop="method" label="方法" width="90" />
      <el-table-column prop="status_code" label="状态码" width="100" />
      <el-table-column prop="client_ip" label="IP" width="140" />
      <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
      <el-table-column prop="query_string" label="Query" min-width="180" show-overflow-tooltip />
      <el-table-column prop="request_body" label="请求体" min-width="220" show-overflow-tooltip />
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadLogs"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";
import { withAdminApiPrefix } from "../lib/adminSecurity";

type AdminOperationLogItem = {
  id: number;
  admin_user_id: number | null;
  username: string | null;
  method: string;
  path: string;
  query_string: string;
  status_code: number;
  client_ip: string | null;
  user_agent: string | null;
  request_body: string;
  created_at: string;
};

const loading = ref(false);
const items = ref<AdminOperationLogItem[]>([]);
const keyword = ref("");
const total = ref(0);
const page = ref(1);
const pageSize = 20;

async function loadLogs() {
  loading.value = true;
  try {
    const params: Record<string, string | number> = {
      limit: pageSize,
      offset: (page.value - 1) * pageSize
    };
    if (keyword.value.trim()) params.keyword = keyword.value.trim();
    const { data } = await api.get<{ items: AdminOperationLogItem[]; total: number }>(
      withAdminApiPrefix("/operation-logs"),
      { params }
    );
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载日志失败");
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  page.value = 1;
  void loadLogs();
}

function formatTime(v: string) {
  return new Date(v).toLocaleString();
}

onMounted(() => {
  void loadLogs();
});
</script>
