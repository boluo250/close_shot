<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>标签用户画像</span>
        <el-button :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </template>

    <el-alert
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="记录 OpenID、最后活跃、地理位置、收藏偏好、会员状态，并自动打标签。"
    />

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="8">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索昵称或 OpenID"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
      </el-col>
      <el-col :span="4">
        <el-select v-model="role" clearable placeholder="角色" @change="onSearch">
          <el-option label="客户" value="customer" />
          <el-option label="摄影师" value="photographer" />
          <el-option label="管理员" value="admin" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-checkbox v-model="onlyMember" @change="onSearch">仅会员</el-checkbox>
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="onSearch">搜索</el-button>
      </el-col>
    </el-row>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="user_id" label="用户ID" width="90" />
      <el-table-column prop="display_name" label="昵称" width="140" />
      <el-table-column prop="role" label="角色" width="120" />
      <el-table-column prop="wechat_openid" label="OpenID" min-width="260" show-overflow-tooltip />
      <el-table-column label="最后活跃" width="180">
        <template #default="{ row }">
          {{ formatTime(row.last_active_at) }}
        </template>
      </el-table-column>
      <el-table-column label="地理位置" width="180">
        <template #default="{ row }">
          <span v-if="row.last_lat !== null && row.last_lng !== null">
            {{ row.last_lat.toFixed(4) }}, {{ row.last_lng.toFixed(4) }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="会员状态" width="140">
        <template #default="{ row }">
          <el-tag :type="row.is_member ? 'success' : 'info'" size="small">
            {{ row.is_member ? "会员" : "非会员" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="收藏了谁" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.favorite_photographers.length">
            {{ row.favorite_photographers.join(" / ") }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="favorite_count" label="收藏数" width="100" />
      <el-table-column label="标签" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag
            v-for="tag in row.tags"
            :key="`${row.user_id}-${tag}`"
            size="small"
            style="margin-right: 6px; margin-bottom: 4px"
          >
            {{ tag }}
          </el-tag>
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

type UserPortraitItem = {
  user_id: number;
  display_name: string | null;
  role: string;
  wechat_openid: string | null;
  is_member: boolean;
  member_expires_at: string | null;
  last_active_at: string | null;
  last_lat: number | null;
  last_lng: number | null;
  favorite_count: number;
  favorite_photographers: string[];
  tags: string[];
};

const loading = ref(false);
const items = ref<UserPortraitItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const keyword = ref("");
const role = ref("");
const onlyMember = ref(false);

async function loadData() {
  loading.value = true;
  try {
    const params: Record<string, string | number | boolean> = {
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
      only_member: onlyMember.value
    };
    if (keyword.value.trim()) params.keyword = keyword.value.trim();
    if (role.value) params.role = role.value;
    const { data } = await api.get<{ items: UserPortraitItem[]; total: number }>(
      withAdminApiPrefix("/user-portraits"),
      { params }
    );
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载用户画像失败");
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  page.value = 1;
  void loadData();
}

function formatTime(v: string | null) {
  if (!v) return "-";
  return new Date(v).toLocaleString();
}

onMounted(() => {
  void loadData();
});
</script>

