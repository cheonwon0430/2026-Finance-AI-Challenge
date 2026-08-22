// 화면 구성을 위한 가짜 데이터 목록입니다. 
// 추후 삭제할 파일입니다.

export interface CompanyFinancial {
  year: number;
  revenue: number;
  operatingProfit: number;
  assets: number;
  liabilities: number;
}

export interface CompanyInvestment {
  date: string;
  stage: string;
  amount: number;
  investors: string[];
}

export interface CompanyPatent {
  title: string;
  applicationNumber: string;
  registrationNumber: string | null;
  applicationDate: string;
  registrationDate: string | null;
  status: string;
}

export interface CompanyNews {
  title: string;
  publisher: string;
  publishedAt: string;
  url: string;
}

export interface Company {
  id: number;
  name: string;
  representative: string;
  foundedAt: string;
  industry: string;
  category: string;
  address: string;
  companySize: string;

  description: string;

  financials: CompanyFinancial[];
  investments: CompanyInvestment[];
  patents: CompanyPatent[];
  news: CompanyNews[];

  summary: {
    overview: string;
    financial: string;
    investment: string;
    patent: string;
  };
}

export const COMPANY_DATA: Company[] = [
  {
    id: 1,
    name: '핀라이트',
    representative: '김민준',
    foundedAt: '2021-03-15',
    industry: '핀테크',
    category: '결제',
    address: '서울특별시 강남구',
    companySize: '중소기업',

    description:
      '온라인 결제 및 정산 인프라를 제공하는 핀테크 기업입니다.',

    financials: [
      {
        year: 2023,
        revenue: 5200000000,
        operatingProfit: 380000000,
        assets: 7800000000,
        liabilities: 3200000000,
      },
      {
        year: 2024,
        revenue: 7100000000,
        operatingProfit: 620000000,
        assets: 10200000000,
        liabilities: 4100000000,
      },
      {
        year: 2025,
        revenue: 9800000000,
        operatingProfit: 910000000,
        assets: 13700000000,
        liabilities: 4900000000,
      },
    ],

    investments: [
      {
        date: '2025-08-12',
        stage: 'Series A',
        amount: 5000000000,
        investors: ['라이트벤처스', '크루인베스트'],
      },
      {
        date: '2023-11-20',
        stage: 'Seed',
        amount: 2500000000,
        investors: ['스타트업파트너스'],
      },
    ],

    patents: [
      {
        title: '결제 이상거래 탐지 시스템',
        applicationNumber: '10-2024-0012345',
        registrationNumber: '10-2678901',
        applicationDate: '2024-02-15',
        registrationDate: '2025-07-10',
        status: '등록',
      },
      {
        title: '다중 결제수단 통합 정산 방법',
        applicationNumber: '10-2024-0078912',
        registrationNumber: null,
        applicationDate: '2024-06-21',
        registrationDate: null,
        status: '심사중',
      },
      {
        title: '실시간 결제 위험도 분석 방법',
        applicationNumber: '10-2023-0123456',
        registrationNumber: '10-2567890',
        applicationDate: '2023-09-18',
        registrationDate: '2024-12-05',
        status: '등록',
      },
    ],

    news: [
      {
        title: '핀라이트, 신규 결제 인프라 서비스 출시',
        publisher: '테크뉴스',
        publishedAt: '2026-07-15',
        url: '#',
      },
      {
        title: '핀라이트, Series A 투자 유치',
        publisher: '스타트업데일리',
        publishedAt: '2025-08-13',
        url: '#',
      },
      {
        title: '핀라이트, 이상거래 탐지 기술 고도화',
        publisher: '핀테크저널',
        publishedAt: '2025-05-02',
        url: '#',
      },
    ],

    summary: {
      overview:
        '핀라이트는 2021년 설립된 결제 분야 핀테크 기업으로 온라인 결제 및 정산 인프라를 제공하고 있습니다.',
      financial:
        '2023년부터 2025년까지 매출과 영업이익이 증가했으며 2025년 매출은 약 98억원입니다.',
      investment:
        'Seed 및 Series A 투자를 통해 총 75억원의 투자를 유치한 것으로 가정한 데이터입니다.',
      patent:
        '결제 및 이상거래 탐지와 관련된 특허 3건이 확인되며 이 중 2건은 등록 상태입니다.',
    },
  },

  {
    id: 2,
    name: '데이터브릿지',
    representative: '이서준',
    foundedAt: '2020-08-21',
    industry: '핀테크',
    category: '금융 데이터',
    address: '서울특별시 영등포구',
    companySize: '중소기업',

    description:
      '금융 데이터를 수집·분석하여 기업과 금융기관에 제공하는 데이터 핀테크 기업입니다.',

    financials: [
      {
        year: 2023,
        revenue: 4300000000,
        operatingProfit: -120000000,
        assets: 6200000000,
        liabilities: 2800000000,
      },
      {
        year: 2024,
        revenue: 5800000000,
        operatingProfit: 210000000,
        assets: 7900000000,
        liabilities: 3100000000,
      },
      {
        year: 2025,
        revenue: 7600000000,
        operatingProfit: 580000000,
        assets: 9600000000,
        liabilities: 3500000000,
      },
    ],

    investments: [
      {
        date: '2024-04-18',
        stage: 'Series A',
        amount: 6000000000,
        investors: ['데이터인베스트', '핀테크벤처스'],
      },
    ],

    patents: [
      {
        title: '금융 데이터 분석 시스템',
        applicationNumber: '10-2023-0034567',
        registrationNumber: '10-2456789',
        applicationDate: '2023-03-12',
        registrationDate: '2024-08-20',
        status: '등록',
      },
    ],

    news: [
      {
        title: '데이터브릿지, 기업 금융 데이터 플랫폼 공개',
        publisher: '비즈니스뉴스',
        publishedAt: '2026-06-20',
        url: '#',
      },
      {
        title: '데이터브릿지, 금융 데이터 분석 서비스 확대',
        publisher: '테크인사이드',
        publishedAt: '2025-12-11',
        url: '#',
      },
    ],

    summary: {
      overview:
        '데이터브릿지는 금융 데이터를 수집하고 분석하여 기업과 금융기관에 제공하는 핀테크 기업입니다.',
      financial:
        '최근 3년간 매출이 증가했으며 2025년에는 영업이익 흑자를 기록한 것으로 가정했습니다.',
      investment:
        'Series A 투자에서 60억원을 유치한 것으로 가정한 데이터입니다.',
      patent:
        '금융 데이터 분석 시스템과 관련된 등록 특허 1건이 확인됩니다.',
    },
  },

  {
    id: 3,
    name: '인슈어랩',
    representative: '박지훈',
    foundedAt: '2022-01-10',
    industry: '핀테크',
    category: '보험',
    address: '서울특별시 마포구',
    companySize: '중소기업',

    description:
      'AI와 데이터를 활용한 보험 업무 자동화 솔루션을 제공하는 핀테크 기업입니다.',

    financials: [
      {
        year: 2023,
        revenue: 1800000000,
        operatingProfit: -450000000,
        assets: 3300000000,
        liabilities: 1700000000,
      },
      {
        year: 2024,
        revenue: 2900000000,
        operatingProfit: -180000000,
        assets: 4100000000,
        liabilities: 1900000000,
      },
      {
        year: 2025,
        revenue: 4700000000,
        operatingProfit: 120000000,
        assets: 5900000000,
        liabilities: 2300000000,
      },
    ],

    investments: [
      {
        date: '2025-03-05',
        stage: 'Pre-Series A',
        amount: 3500000000,
        investors: ['퓨처핀', '임팩트벤처스'],
      },
    ],

    patents: [
      {
        title: '보험금 청구 자동화 시스템',
        applicationNumber: '10-2024-0098765',
        registrationNumber: null,
        applicationDate: '2024-07-04',
        registrationDate: null,
        status: '심사중',
      },
      {
        title: '보험 서류 분석 방법',
        applicationNumber: '10-2023-0054321',
        registrationNumber: '10-2671234',
        applicationDate: '2023-04-11',
        registrationDate: '2025-06-01',
        status: '등록',
      },
    ],

    news: [
      {
        title: '인슈어랩, 보험 업무 자동화 솔루션 공개',
        publisher: 'AI뉴스',
        publishedAt: '2026-05-14',
        url: '#',
      },
      {
        title: '인슈어랩, 보험사 대상 B2B 사업 확대',
        publisher: '핀테크뉴스',
        publishedAt: '2025-10-22',
        url: '#',
      },
    ],

    summary: {
      overview:
        '인슈어랩은 AI와 금융 데이터를 활용해 보험 업무를 자동화하는 핀테크 기업입니다.',
      financial:
        '최근 매출이 증가하고 있으며 2025년 영업이익 흑자 전환을 가정한 데이터입니다.',
      investment:
        'Pre-Series A 단계에서 35억원을 유치한 것으로 가정했습니다.',
      patent:
        '보험금 청구 및 서류 분석과 관련된 특허 2건이 확인됩니다.',
    },
  },
];

export const getCompanyById = (companyId: number) => {
  return COMPANY_DATA.find((company) => company.id === companyId);
};

export const searchCompanies = (query: string) => {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) {
    return COMPANY_DATA;
  }

  return COMPANY_DATA.filter((company) =>
    company.name.toLowerCase().includes(normalizedQuery),
  );
};