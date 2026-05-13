<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>操作日志中心</span>
        <el-button :loading="loading" @click="refreshCurrentTab">刷新</el-button>
      </div>
    </template>

    <el-alert
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="管理员日志记录后台接口审计；用户日志记录小程序与摄影师工作台的关键操作，包含登录、收藏、认证提交、上传、资料维护、套餐/作品/档期变更等。"
    />

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="后台操作日志" name="admin">
        <el-row :gutter="12" style="margin-bottom: 12px">
          <el-col :span="8">
            <el-input
              v-model="adminKeyword"
              clearable
              placeholder="搜索账号 / 方法 / 路径"
              @keyup.enter="onAdminSearch"
              @clear="onAdminSearch"
            />
          </el-col>
          <el-col :span="4">
            <el-button type="primary" @click="onAdminSearch">搜索</el-button>
          </el-col>
        </el-row>

        <el-table :data="adminItems" v-loading="loading" stripe>
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
          <el-table-column prop="request_body" label="请求体" min-width="240" show-overflow-tooltip />
        </el-table>

        <div style="display: flex; justify-content: flex-end; margin-top: 16px">
          <el-pagination
            v-model:current-page="adminPage"
            :page-size="pageSize"
            :total="adminTotal"
            layout="total, prev, pager, next"
            @current-change="loadAdminLogs"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="用户操作日志" name="user">
        <el-row :gutter="12" style="margin-bottom: 12px">
          <el-col :span="8">
            <el-input
              v-model="userKeyword"
              clearable
              placeholder="搜索用户 / 动作 / 路径 / 资源"
              @keyup.enter="onUserSearch"
              @clear="onUserSearch"
            />
          </el-col>
          <el-col :span="4">
            <el-select v-model="userRole" clearable placeholder="角色" style="width: 100%">
              <el-option label="普通用户" value="customer" />
              <el-option label="摄影师" value="photographer" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="userChannel" clearable placeholder="来源端" style="width: 100%">
              <el-option label="小程序" value="mini_program" />
              <el-option label="摄影师后台" value="studio_web" />
              <el-option label="运营后台" value="ops_web" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-button type="primary" @click="onUserSearch">搜索</el-button>
          </el-col>
        </el-row>

        <el-table :data="userItems" v-loading="loading" stripe>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column label="时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="用户" min-width="180">
            <template #default="{ row }">
              {{ row.actor_name || "-" }}
            </template>
          </el-table-column>
          <el-table-column label="角色" width="110">
            <template #default="{ row }">
              {{ formatRole(row.actor_role) }}
            </template>
          </el-table-column>
          <el-table-column label="来源端" width="120">
            <template #default="{ row }">
              {{ formatChannel(row.channel) }}
            </template>
          </el-table-column>
          <el-table-column prop="action_label" label="动作" width="160" show-overflow-tooltip />
          <el-table-column prop="status_code" label="状态码" width="100" />
          <el-table-column prop="resource_type" label="资源类型" width="140" show-overflow-tooltip />
          <el-table-column prop="resource_id" label="资源 ID" min-width="160" show-overflow-tooltip />
          <el-table-column prop="path" label="路径" min-width="200" show-overflow-tooltip />
          <el-table-column prop="client_ip" label="IP" width="140" />
          <el-table-column prop="request_body" label="请求体" min-width="240" show-overflow-tooltip />
        </el-table>

        <div style="display: flex; justify-content: flex-end; margin-top: 16px">
          <el-pagination
            v-model:current-page="userPage"
            :page-size="pageSize"
            :total="userTotal"
            layout="total, prev, pager, next"
            @current-change="loadUserLogs"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
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

type UserOperationLogItem = {
  id: number;
  user_id: number | null;
  actor_name: string | null;
  actor_role: string | null;
  channel: string | null;
  action: string;
  action_label: string;
  resource_type: string;
  resource_id: string | null;
  method: string;
  path: string;
  query_string: string;
  status_code: number;
  client_ip: string | null;
  user_agent: string | null;
  request_body: string;
  created_at: string;
};

const activeTab = ref<"admin" | "user">("admin");
const loading = ref(false);
const pageSize = 20;

const adminItems = ref<AdminOperationLogItem[]>([]);
const adminKeyword = ref("");
const adminTotal = ref(0);
const adminPage = ref(1);

const userItems = ref<UserOperationLogItem[]>([]);
const userKeyword = ref("");
const userRole = ref("");
const userChannel = ref("");
const userTotal = ref(0);
const userPage = ref(1);

async function loadAdminLogs() {
  loading.value = true;
  try {
    const params: Record<string, string | number> = {
      limit: pageSize,
      offset: (adminPage.value - 1) * pageSize
    };
    if (adminKeyword.value.trim()) params.keyword = adminKeyword.value.trim();
    const { data } = await api.get<{ items: AdminOperationLogItem[]; total: number }>(
      withAdminApiPrefix("/operation-logs"),
      { params }
    );
    adminItems.value = data.items || [];
    adminTotal.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载后台操作日志失败");
  } finally {
    loading.value = false;
  }
}

async function loadUserLogs() {
  loading.value = true;
  try {
    const params: Record<string, string | number> = {
      limit: pageSize,
      offset: (userPage.value - 1) * pageSize
    };
    if (userKeyword.value.trim()) params.keyword = userKeyword.value.trim();
    if (userRole.value) params.actor_role = userRole.value;
    if (userChannel.value) params.channel = userChannel.value;
    const { data } = await api.get<{ items: UserOperationLogItem[]; total: number }>(
      withAdminApiPrefix("/user-operation-logs"),
      { params }
    );
    userItems.value = data.items || [];
    userTotal.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载用户操作日志失败");
  } finally {
    loading.value = false;
  }
}

function onAdminSearch() {
  adminPage.value = 1;
  void loadAdminLogs();
}

function onUserSearch() {
  userPage.value = 1;
  void loadUserLogs();
}

function onTabChange(name: string | number) {
  if (name === "user") {
    void loadUserLogs();
    return;
  }
  void loadAdminLogs();
}

function refreshCurrentTab() {
  if (activeTab.value === "user") {
    void loadUserLogs();
    return;
  }
  void loadAdminLogs();
}

function formatTime(v: string) {
  return new Date(v).toLocaleString();
}

function formatRole(role: string | null) {
  if (role === "customer") return "普通用户";
  if (role === "photographer") return "摄影师";
  if (role === "admin") return "管理员";
  return role || "-";
}

function formatChannel(channel: string | null) {
  if (channel === "mini_program") return "小程序";
  if (channel === "studio_web") return "摄影师后台";
  if (channel === "ops_web") return "运营后台";
  return channel || "-";
}

onMounted(() => {
  void loadAdminLogs();
});
</script>
