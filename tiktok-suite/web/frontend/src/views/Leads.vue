<template>
  <div>
    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="关键词">
          <el-input v-model="filters.q" placeholder="用户名 / 评论内容" clearable style="width: 220px"
            @keyup.enter="load" @clear="load" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 130px" @change="load">
            <el-option v-for="s in LEAD_STATUS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="filters.lang" placeholder="全部" clearable style="width: 110px" @change="load">
            <el-option v-for="l in LANGS" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item label="地区">
          <el-select v-model="filters.region" placeholder="全部" clearable filterable style="width: 150px" @change="load">
            <el-option v-for="r in regions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="'Search'" @click="load">查询</el-button>
          <el-button :icon="'Refresh'" @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 线索表格 -->
    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" @row-click="openDetail" row-key="id" style="cursor: pointer">
        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="nickname">{{ row.nickname || '-' }}</div>
            <div class="username">@{{ row.username }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="100" />
        <el-table-column prop="language" label="语言" width="80" />
        <el-table-column label="意向分" width="100" sortable :sort-method="(a, b) => a.intent_score - b.intent_score">
          <template #default="{ row }">
            <el-tag :type="scoreType(row.intent_score)" effect="dark">{{ row.intent_score ?? 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(LEAD_STATUS, row.status)">{{ statusLabel(LEAD_STATUS, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="followers" label="粉丝数" width="100" sortable />
        <el-table-column label="WhatsApp" width="140">
          <template #default="{ row }">
            <el-link v-if="row.whatsapp" type="success" :href="'https://wa.me/' + row.whatsapp" target="_blank">
              {{ row.whatsapp }}
            </el-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="最近互动" width="170">
          <template #default="{ row }">{{ fmtTime(row.last_interaction_at) }}</template>
        </el-table-column>
        <template #empty><el-empty description="暂无线索" /></template>
      </el-table>
      <div class="pager">
        <span class="total">共 {{ total }} 条</span>
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="pageSize"
          :current-page="page" @current-change="onPage" />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawer" :title="detail.nickname ? detail.nickname + ' (@' + detail.username + ')' : '线索详情'"
      size="520px">
      <div v-loading="detailLoading">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="地区">{{ detail.region || '-' }} / {{ detail.language || '-' }}</el-descriptions-item>
          <el-descriptions-item label="粉丝">{{ detail.followers ?? 0 }} / 关注 {{ detail.following_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="WhatsApp">
            <el-link v-if="detail.whatsapp" type="success" :href="'https://wa.me/' + detail.whatsapp" target="_blank">
              {{ detail.whatsapp }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="评论原文">
            <div class="comment-text">{{ detail.comment_text || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="Bio">
            <div class="comment-text">{{ detail.bio || '-' }}</div>
          </el-descriptions-item>
        </el-descriptions>

        <div class="section-title">状态</div>
        <el-select v-model="editStatus" style="width: 200px">
          <el-option v-for="s in LEAD_STATUS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button type="primary" style="margin-left: 8px" @click="saveStatus" :loading="saving">保存状态</el-button>

        <div class="section-title">备注</div>
        <el-input v-model="editNotes" type="textarea" :rows="3" placeholder="添加备注..." />
        <el-button type="primary" style="margin-top: 8px" @click="saveNotes" :loading="saving">保存备注</el-button>

        <div class="section-title">互动历史</div>
        <el-timeline v-if="interactions.length">
          <el-timeline-item v-for="it in interactions" :key="it.id" :timestamp="fmtTime(it.created_at)"
            :type="statusTag(INTERACTION_STATUS, it.status)">
            <el-tag size="small" :type="statusTag(ACTION_TYPES, it.action_type)" style="margin-right: 6px">
              {{ statusLabel(ACTION_TYPES, it.action_type) }}
            </el-tag>
            <el-tag size="small" :type="statusTag(INTERACTION_STATUS, it.status)">
              {{ statusLabel(INTERACTION_STATUS, it.status) }}
            </el-tag>
            <div class="it-content">{{ it.content || it.platform_msg || '-' }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无互动记录" :image-size="60" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import dayjs from 'dayjs';
import http from '../api';
import { LEAD_STATUS, ACTION_TYPES, INTERACTION_STATUS, LANGS, statusLabel, statusTag, scoreType } from '../utils/constants';

const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const loading = ref(false);
const filters = reactive({ q: '', status: '', lang: '', region: '' });
const regions = ref([]); // 地区下拉选项，来自当前结果去重

const drawer = ref(false);
const detailLoading = ref(false);
const detail = ref({});
const interactions = ref([]);
const editStatus = ref('');
const editNotes = ref('');
const saving = ref(false);

const fmtTime = (t) => (t ? dayjs(t).format('MM-DD HH:mm') : '-');

async function load() {
  loading.value = true;
  try {
    const data = await http.get('/leads', {
      params: { ...filters, limit: pageSize, offset: (page.value - 1) * pageSize },
    });
    rows.value = data.items || [];
    total.value = data.total ?? rows.value.length;
    // 地区选项取结果去重 + 已有筛选，保证下拉有值
    const set = new Set(regions.value);
    rows.value.forEach((r) => r.region && set.add(r.region));
    if (filters.region) set.add(filters.region);
    regions.value = [...set];
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(filters, { q: '', status: '', lang: '', region: '' });
  page.value = 1;
  load();
}

function onPage(p) {
  page.value = p;
  load();
}

// 行点击打开详情抽屉
async function openDetail(row) {
  drawer.value = true;
  detailLoading.value = true;
  try {
    const data = await http.get(`/leads/${row.id}`);
    detail.value = data;
    interactions.value = data.interactions || [];
    editStatus.value = data.status;
    editNotes.value = data.notes || '';
  } finally {
    detailLoading.value = false;
  }
}

async function patchLead(body) {
  saving.value = true;
  try {
    const updated = await http.patch(`/leads/${detail.value.id}`, body);
    Object.assign(detail.value, updated);
    // 同步列表行
    const row = rows.value.find((r) => r.id === updated.id);
    if (row) Object.assign(row, updated);
  } finally {
    saving.value = false;
  }
}

const saveStatus = () => patchLead({ status: editStatus.value });
const saveNotes = () => patchLead({ notes: editNotes.value });

onMounted(load);
</script>

<style scoped>
.filter-card { margin-bottom: 12px; }
.nickname { font-weight: 600; }
.username { color: #909399; font-size: 12px; }
.pager { margin-top: 12px; display: flex; align-items: center; gap: 16px; justify-content: flex-end; }
.total { color: #909399; font-size: 13px; }
.section-title { font-weight: 600; margin: 16px 0 8px; }
.comment-text { white-space: pre-wrap; word-break: break-all; }
.it-content { margin-top: 4px; color: #606266; font-size: 13px; }
</style>
