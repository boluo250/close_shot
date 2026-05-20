<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>风险标记 / 黑名单</span>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="5">
        <el-select v-model="filters.risk_level" placeholder="风险等级" clearable @change="load">
          <el-option label="全部等级" value="" />
          <el-option label="低风险" value="low" />
          <el-option label="中风险" value="medium" />
          <el-option label="高风险" value="high" />
        </el-select>
      </el-col>
      <el-col :span="5">
        <el-select v-model="filters.blacklist_status" placeholder="黑名单状态" clearable @change="load">
          <el-option label="全部状态" value="" />
          <el-option label="正常" value="normal" />
          <el-option label="观察名单" value="watch" />
          <el-option label="已拉黑" value="blocked" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索昵称 / 姓名 / 手机号"
          clearable
          @keyup.enter="load"
          @clear="load"
        />
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="load">搜索</el-button>
      </el-col>
    </el-row>

    <el-table :data="items" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="user_id" label="用户ID" width="90" />
      <el-table-column label="昵称" min-width="140">
        <template #default="{ row }">
          {{ row.display_name || "-" }}
        </template>
      </el-table-column>
      <el-table-column label="角色" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="row.role === 'photographer' ? 'success' : row.role === 'admin' ? 'danger' : 'info'">
            {{ roleLabel(row.role) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="手机号" width="130">
        <template #default="{ row }">
          {{ row.phone || "-" }}
        </template>
      </el-table-column>
      <el-table-column label="履约分" width="100">
        <template #default="{ row }">
          <span :style="{ color: scoreColor(row.trust_score), fontWeight: 600 }">{{ row.trust_score }}</span>
        </template>
      </el-table-column>
      <el-table-column label="风险等级" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="riskTagType(row.risk_level)">
            {{ riskLabel(row.risk_level) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="黑名单状态" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="blacklistTagType(row.blacklist_status)">
            {{ blacklistLabel(row.blacklist_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="摄影师状态" width="120">
        <template #default="{ row }">
          {{ photographerStatusLabel(row.photographer_status) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>

  <el-dialog v-model="dialogVisible" title="编辑风险状态" width="460px">
    <el-form v-if="currentItem" label-width="96px">
      <el-form-item label="用户">
        <div>{{ currentItem.display_name || `#${currentItem.user_id}` }}</div>
      </el-form-item>
      <el-form-item label="履约分">
        <el-input-number v-model="form.trust_score" :min="0" :max="100" style="width: 160px" />
      </el-form-item>
      <el-form-item label="风险等级">
        <el-select v-model="form.risk_level" style="width: 180px">
          <el-option label="低风险" value="low" />
          <el-option label="中风险" value="medium" />
          <el-option label="高风险" value="high" />
        </el-select>
      </el-form-item>
      <el-form-item label="黑名单">
        <el-select v-model="form.blacklist_status" style="width: 180px">
          <el-option label="正常" value="normal" />
          <el-option label="观察名单" value="watch" />
          <el-option label="已拉黑" value="blocked" />
        </el-select>
      </el-form-item>
      <el-alert
        v-if="form.blacklist_status === 'blocked'"
        type="warning"
        :closable="false"
        title="拉黑后将阻止该账号继续提交入驻申请，摄影师账号也会自动下线。"
      />
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";
import { withAdminApiPrefix } from "../lib/adminSecurity";

type RiskUserItem = {
  user_id: number;
  display_name: string | null;
  role: string;
  photographer_status: string | null;
  phone: string | null;
  real_name: string | null;
  is_member: boolean;
  trust_score: number;
  risk_level: string;
  blacklist_status: string;
  created_at: string;
  updated_at: string;
};

const loading = ref(false);
const saving = ref(false);
const items = ref<RiskUserItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;

const filters = reactive({
  risk_level: "",
  blacklist_status: "",
  keyword: ""
});

const dialogVisible = ref(false);
const currentItem = ref<RiskUserItem | null>(null);
const form = reactive({
  trust_score: 70,
  risk_level: "low",
  blacklist_status: "normal"
});

async function load() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      limit: pageSize,
      offset: (page.value - 1) * pageSize
    };
    if (filters.risk_level) params.risk_level = filters.risk_level;
    if (filters.blacklist_status) params.blacklist_status = filters.blacklist_status;
    if (filters.keyword) params.keyword = filters.keyword;

    const { data } = await api.get<{ items: RiskUserItem[]; total: number }>(
      withAdminApiPrefix("/risk-users"),
      { params }
    );
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载风险列表失败");
  } finally {
    loading.value = false;
  }
}

function openEdit(row: RiskUserItem) {
  currentItem.value = row;
  form.trust_score = row.trust_score;
  form.risk_level = row.risk_level || "low";
  form.blacklist_status = row.blacklist_status || "normal";
  dialogVisible.value = true;
}

async function save() {
  if (!currentItem.value) return;
  saving.value = true;
  try {
    const { data } = await api.put<RiskUserItem>(
      withAdminApiPrefix(`/risk-users/${currentItem.value.user_id}`),
      {
        trust_score: form.trust_score,
        risk_level: form.risk_level,
        blacklist_status: form.blacklist_status
      }
    );
    const idx = items.value.findIndex((item) => item.user_id === data.user_id);
    if (idx >= 0) items.value[idx] = data;
    currentItem.value = data;
    dialogVisible.value = false;
    ElMessage.success("风险状态已更新");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

function roleLabel(role: string) {
  if (role === "admin") return "管理员";
  if (role === "photographer") return "摄影师";
  return "普通用户";
}

function riskLabel(level: string) {
  if (level === "high") return "高风险";
  if (level === "medium") return "中风险";
  return "低风险";
}

function riskTagType(level: string) {
  if (level === "high") return "danger";
  if (level === "medium") return "warning";
  return "success";
}

function blacklistLabel(status: string) {
  if (status === "blocked") return "已拉黑";
  if (status === "watch") return "观察名单";
  return "正常";
}

function blacklistTagType(status: string) {
  if (status === "blocked") return "danger";
  if (status === "watch") return "warning";
  return "info";
}

function photographerStatusLabel(status: string | null) {
  if (status === "approved") return "已通过";
  if (status === "pending") return "审核中";
  if (status === "rejected") return "未通过";
  return "-";
}

function scoreColor(score: number) {
  if (score < 60) return "#d03050";
  if (score < 80) return "#b88230";
  return "#2f7d32";
}

onMounted(load);
</script>
