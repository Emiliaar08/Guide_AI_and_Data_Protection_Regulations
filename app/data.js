// Метаданные статей из corpus/docs.jsonl. Ответы чата поступают только из API.
window.NavigatorData = (() => {
  const documents = [
  {
    "id": "152fz",
    "short": "152-ФЗ",
    "title": "Федеральный закон «О персональных данных»",
    "jurisdiction": "Россия",
    "mark": "РФ",
    "tone": "ru",
    "description": "Федеральный закон «О персональных данных»",
    "url": "https://mintrud.gov.ru/docs/laws/130"
  },
  {
    "id": "gdpr",
    "short": "GDPR",
    "title": "General Data Protection Regulation",
    "jurisdiction": "Европейский союз",
    "mark": "EU",
    "tone": "eu",
    "description": "General Data Protection Regulation",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng"
  },
  {
    "id": "ai-act",
    "short": "AI Act",
    "title": "Artificial Intelligence Act",
    "jurisdiction": "Европейский союз",
    "mark": "AI",
    "tone": "ai",
    "description": "Artificial Intelligence Act",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng"
  }
];
  const articles = [
  {
    "id": "152fz:3",
    "documentId": "152fz",
    "number": "3",
    "title": "Основные понятия, используемые в настоящем Федеральном законе",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D01"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:5",
    "documentId": "152fz",
    "number": "5",
    "title": "Принципы обработки персональных данных",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D02"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:6",
    "documentId": "152fz",
    "number": "6",
    "title": "Условия обработки персональных данных",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D03",
      "D04"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:9",
    "documentId": "152fz",
    "number": "9",
    "title": "Согласие субъекта персональных данных на обработку его персональных данных",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D05"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:10",
    "documentId": "152fz",
    "number": "10",
    "title": "Специальные категории персональных данных",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D06"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:11",
    "documentId": "152fz",
    "number": "11",
    "title": "Биометрические персональные данные",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D07"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:12",
    "documentId": "152fz",
    "number": "12",
    "title": "Трансграничная передача персональных данных",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D08"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:16",
    "documentId": "152fz",
    "number": "16",
    "title": "Права субъектов персональных данных при принятии решений на основании исключительно автоматизированной обработки их персональных данных",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D09"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "152fz:18.1",
    "documentId": "152fz",
    "number": "18.1",
    "title": "Меры, направленные на обеспечение выполнения оператором обязанностей, предусмотренных настоящим Федеральным законом",
    "url": "https://mintrud.gov.ru/docs/laws/130",
    "fragmentIds": [
      "D10"
    ],
    "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)"
  },
  {
    "id": "gdpr:4",
    "documentId": "gdpr",
    "number": "4",
    "title": "Определения",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D11"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:5",
    "documentId": "gdpr",
    "number": "5",
    "title": "Принципы, касающиеся обработки персональных данных",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D12"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:6",
    "documentId": "gdpr",
    "number": "6",
    "title": "Законность обработки",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D13"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:9",
    "documentId": "gdpr",
    "number": "9",
    "title": "Обработка специальных категорий персональных данных",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D14"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:22",
    "documentId": "gdpr",
    "number": "22",
    "title": "Автоматизированное принятие решений в индивидуальных случаях, в том числе профилирование",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D15"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:28",
    "documentId": "gdpr",
    "number": "28",
    "title": "Процессор",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D16",
      "D17"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:35",
    "documentId": "gdpr",
    "number": "35",
    "title": "Оценка воздействия на защиту персональных данных",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D18"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:44",
    "documentId": "gdpr",
    "number": "44",
    "title": "Общий принцип передачи",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D19"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "gdpr:46",
    "documentId": "gdpr",
    "number": "46",
    "title": "Передача данных при условии осуществления надлежащих гарантий",
    "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
    "fragmentIds": [
      "D20"
    ],
    "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод"
  },
  {
    "id": "ai-act:3",
    "documentId": "ai-act",
    "number": "3",
    "title": "Определения",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D21"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:4",
    "documentId": "ai-act",
    "number": "4",
    "title": "ИИ-грамотность",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D22"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:5",
    "documentId": "ai-act",
    "number": "5",
    "title": "Запрещённые практики в области ИИ",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D23"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:6",
    "documentId": "ai-act",
    "number": "6",
    "title": "Правила классификации систем ИИ высокого риска",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D24"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:10",
    "documentId": "ai-act",
    "number": "10",
    "title": "Данные и управление данными",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D25"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:14",
    "documentId": "ai-act",
    "number": "14",
    "title": "Человеческий надзор",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D26"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:26",
    "documentId": "ai-act",
    "number": "26",
    "title": "Обязанности эксплуатантов систем ИИ высокого риска",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D27",
      "D28"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:50",
    "documentId": "ai-act",
    "number": "50",
    "title": "Обязанности по обеспечению прозрачности для поставщиков и эксплуатантов определённых систем ИИ",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D29"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  },
  {
    "id": "ai-act:53",
    "documentId": "ai-act",
    "number": "53",
    "title": "Обязанности поставщиков моделей ИИ общего назначения",
    "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
    "fragmentIds": [
      "D30"
    ],
    "edition": "консолидированная редакция от 27.07.2026 (с изменениями Регламента (ЕС) 2026/1744); неофициальный перевод"
  }
];
  const scenarios = [
    { tag: 'Персональные данные', title: 'Данные в ИИ-сервисе', text: 'Разберитесь, какие нормы относятся к обработке данных в вашем продукте.', query: 'Какие статьи стоит изучить при обработке персональных данных в ИИ-сервисе?' },
    { tag: 'Поставщики', title: 'Внешний поставщик технологии', text: 'Найдите статьи об обработчиках и использовании внешних API.', query: 'Какие статьи относятся к передаче персональных данных внешнему поставщику API?' },
    { tag: 'Обучение модели', title: 'Данные для обучения', text: 'Начните с принципов и оснований обработки персональных данных.', query: 'Какие статьи о персональных данных нужно изучить для обучения модели?' },
    { tag: 'Трансграничная передача', title: 'Передача между странами', text: 'Найдите положения о передаче персональных данных за рубеж.', query: 'Какие статьи посвящены трансграничной передаче персональных данных?' },
    { tag: 'Контроль человека', title: 'Надзор за ИИ-системой', text: 'Изучите статьи AI Act о человеческом надзоре и использовании ИИ.', query: 'Какие статьи AI Act посвящены человеческому надзору?' },
    { tag: 'Россия и ЕС', title: 'Несколько юрисдикций', text: 'Сопоставьте статьи о данных в документах России и ЕС.', query: 'Какие статьи о персональных данных есть в 152-ФЗ и GDPR?' }
  ];
  return { documents, articles, scenarios };
})();
