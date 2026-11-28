export interface Dims {
  sleep: number
  clean: number
  social: number
  noise: number
  boundary: number
  spend: number
}

export const DIM_META: { key: keyof Dims; label: string }[] = [
  { key: 'sleep', label: '作息' },
  { key: 'clean', label: '整洁' },
  { key: 'social', label: '社交' },
  { key: 'noise', label: '噪声' },
  { key: 'boundary', label: '边界' },
  { key: 'spend', label: '消费' },
]

export interface Candidate {
  id: string
  name: string
  initial: string
  college: string
  grade: string
  tags: string[]
  dims: Dims
  score: number
  headline: string
  note: string
  redline: string
}

export const candidates: Candidate[] = [
  {
    id: 'lin',
    name: '林知夏',
    initial: '林',
    college: '计算机学院',
    grade: '大三',
    tags: ['早睡', '爱干净', '有边界'],
    dims: { sleep: 88, clean: 82, social: 34, noise: 22, boundary: 90, spend: 58 },
    score: 92,
    headline: '23:30 熄灯，周末偶尔做饭',
    note: '不太爱热闹，但愿意一起把公共区域排个值日表。',
    redline: '不接受带人回寝过夜',
  },
  {
    id: 'zhou',
    name: '周予安',
    initial: '周',
    college: '外国语学院',
    grade: '大二',
    tags: ['整洁', '有边界', '周末做饭'],
    dims: { sleep: 74, clean: 92, social: 48, noise: 30, boundary: 86, spend: 66 },
    score: 87,
    headline: '东西有固定位置，周五晚一起做饭',
    note: '可以接受朋友来坐一会儿，提前说一声就好。',
    redline: '不接受在寝室抽烟',
  },
  {
    id: 'chen',
    name: '陈默',
    initial: '陈',
    college: '建筑学院',
    grade: '大四',
    tags: ['夜猫', '安静', '打游戏'],
    dims: { sleep: 28, clean: 64, social: 40, noise: 52, boundary: 72, spend: 48 },
    score: 81,
    headline: '凌晨两点睡，戴耳机打游戏',
    note: '白天基本不在寝室，晚上安静，不介意别人早睡。',
    redline: '不接受早上七点前开灯',
  },
  {
    id: 'su',
    name: '苏晚',
    initial: '苏',
    college: '新闻学院',
    grade: '大二',
    tags: ['社交', '热闹', '养猫'],
    dims: { sleep: 52, clean: 58, social: 92, noise: 70, boundary: 44, spend: 74 },
    score: 76,
    headline: '喜欢朋友来串门，有一只猫',
    note: '会提前问，不会突然带人回来；猫只在寝室活动。',
    redline: '不接受对猫过敏的室友',
  },
  {
    id: 'he',
    name: '何川',
    initial: '何',
    college: '数学学院',
    grade: '大三',
    tags: ['早起', '健身', '整洁'],
    dims: { sleep: 82, clean: 88, social: 56, noise: 26, boundary: 78, spend: 52 },
    score: 74,
    headline: '六点半起床，晚上十一点睡',
    note: '作息很固定，希望室友晚上尽量不外放。',
    redline: '不接受通宵开黑',
  },
  {
    id: 'tang',
    name: '唐梨',
    initial: '唐',
    college: '设计学院',
    grade: '大一',
    tags: ['灵活', '随和', '熬夜'],
    dims: { sleep: 38, clean: 54, social: 76, noise: 58, boundary: 62, spend: 70 },
    score: 69,
    headline: '作息跟着作业走，好说话',
    note: '不挑寝室，愿意配合别人的习惯，只要提前沟通。',
    redline: '不接受冷暴力',
  },
]

export const me = {
  name: '林知夏',
  initial: '林',
  handle: 'zhixia',
  college: '计算机学院',
  major: '软件工程',
  grade: '大三',
  gender: '女',
  room: '4 人寝',
  completeness: 78,
  dims: { sleep: 84, clean: 76, social: 38, noise: 24, boundary: 88, spend: 60 } as Dims,
  tags: ['早睡', '爱干净', '有边界', '周末做饭'],
  redlines: ['不接受带人回寝过夜', '不接受在寝室抽烟', '不接受通宵外放'],
  prompts: [
    {
      title: '一个让我觉得“住得舒服”的细节',
      text: '公共桌面上永远是空的。不是洁癖，是看到空桌面会松一口气。',
    },
    {
      title: '我不能妥协的一件事',
      text: '晚上十二点以后，寝室里不要有外放的声音。耳机可以解决大部分问题。',
    },
    {
      title: '我希望室友怎么跟我沟通',
      text: '直接说。不用绕，也不用忍到第三次才开口，我不会因为被提醒而生气。',
    },
  ],
}

export const dimAverage = (dims: Dims): number =>
  Math.round(Object.values(dims).reduce((sum, value) => sum + value, 0) / 6)
