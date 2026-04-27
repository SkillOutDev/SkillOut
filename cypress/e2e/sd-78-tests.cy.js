const eventsApiPattern = '**/api/events/student/1/'
const eventsPageUrl = 'http://localhost:5173/events'

const makeEvent = ({
  event_id,
  name,
  date,
  time,
  place,
  price,
  categories,
  short_description,
}) => ({
  event_id,
  name,
  date,
  time,
  place,
  price,
  categories,
  short_description,
  source_url: `https://example.com/${name.toLowerCase().replace(/\s+/g, '-')}`,
})

const buildEventsResponse = (events, overrides = {}) => ({
  total: events.length,
  events,
  message: '',
  ...overrides,
})

const visitEventsPage = (responseBody) => {
  cy.intercept('GET', eventsApiPattern, {
    statusCode: 200,
    body: responseBody,
  }).as('loadEvents')

  cy.visit(eventsPageUrl)
  cy.wait('@loadEvents')
}

const assertEventOrder = (expectedNames) => {
  cy.get('.events-list .event-item').should('have.length', expectedNames.length)
  cy.get('.events-list .event-item h2').then(($headers) => {
    const names = [...$headers].map((element) => element.textContent.trim())
    expect(names).to.deep.equal(expectedNames)
  })
}

const technologyBusinessCommunity = [
  makeEvent({
    event_id: 1,
    name: 'Technology Summit',
    date: '2026-05-10',
    time: '09:00',
    place: 'Hall A',
    price: '25.00',
    categories: ['Technology'],
    short_description: 'Technology matches the strongest interest.',
  }),
  makeEvent({
    event_id: 2,
    name: 'Business Expo',
    date: '2026-05-11',
    time: '10:00',
    place: 'Hall B',
    price: '15.00',
    categories: ['Business'],
    short_description: 'Business is the middle interest.',
  }),
  makeEvent({
    event_id: 3,
    name: 'Community Meetup',
    date: '2026-05-12',
    time: '11:00',
    place: 'Hall C',
    price: '5.00',
    categories: ['Community'],
    short_description: 'Community is the lowest interest.',
  }),
]

const businessTechnologyCommunity = [
  technologyBusinessCommunity[1],
  technologyBusinessCommunity[0],
  technologyBusinessCommunity[2],
]

const communityTechnologyBusiness = [
  technologyBusinessCommunity[2],
  technologyBusinessCommunity[0],
  technologyBusinessCommunity[1],
]

const technologyBusinessTie = [
  technologyBusinessCommunity[0],
  technologyBusinessCommunity[1],
  technologyBusinessCommunity[2],
]

const businessTechnologyTie = [
  technologyBusinessCommunity[1],
  technologyBusinessCommunity[0],
  technologyBusinessCommunity[2],
]

const businessCommunityTie = [
  technologyBusinessCommunity[1],
  technologyBusinessCommunity[2],
  technologyBusinessCommunity[0],
]

const dualCategoryTechnologyWins = [
  makeEvent({
    event_id: 11,
    name: 'Dual Focus Tech',
    date: '2026-06-01',
    time: '08:30',
    place: 'Room 101',
    price: '0.00',
    categories: ['Technology', 'Business'],
    short_description: 'The strongest matched category is Technology.',
  }),
  makeEvent({
    event_id: 12,
    name: 'Support Expo',
    date: '2026-06-02',
    time: '09:30',
    place: 'Room 102',
    price: '10.00',
    categories: ['Business'],
    short_description: 'A lower-ranked business event.',
  }),
  makeEvent({
    event_id: 13,
    name: 'Open Community',
    date: '2026-06-03',
    time: '10:30',
    place: 'Room 103',
    price: '5.00',
    categories: ['Community'],
    short_description: 'A lower-ranked community event.',
  }),
]

const dualCategoryBusinessWins = [
  makeEvent({
    event_id: 21,
    name: 'Dual Focus Business',
    date: '2026-06-04',
    time: '08:30',
    place: 'Room 201',
    price: '0.00',
    categories: ['Business', 'Technology'],
    short_description: 'The strongest matched category is Business.',
  }),
  dualCategoryTechnologyWins[0],
  dualCategoryTechnologyWins[2],
]

const dualCategoryCommunityWins = [
  makeEvent({
    event_id: 31,
    name: 'Dual Focus Community',
    date: '2026-06-07',
    time: '08:30',
    place: 'Room 301',
    price: '0.00',
    categories: ['Community', 'Technology'],
    short_description: 'The strongest matched category is Community.',
  }),
  dualCategoryTechnologyWins[0],
  dualCategoryTechnologyWins[1],
]

const singleEventList = [
  makeEvent({
    event_id: 41,
    name: 'Solo Workshop',
    date: '2026-07-01',
    time: '12:15',
    place: 'Lab 1',
    price: '0.00',
    categories: ['Technology'],
    short_description: 'A single event in the list.',
  }),
]

const equalInterestEvents = [
  makeEvent({
    event_id: 51,
    name: 'Conference Alpha',
    date: '2026-07-03',
    time: '09:00',
    place: 'Center A',
    price: '20.00',
    categories: ['Business'],
    short_description: 'First equal-interest event.',
  }),
  makeEvent({
    event_id: 52,
    name: 'Conference Beta',
    date: '2026-07-04',
    time: '10:00',
    place: 'Center B',
    price: '22.00',
    categories: ['Technology'],
    short_description: 'Second equal-interest event.',
  }),
]

describe('SD-78 event ordering', () => {
  it('places the technology event first when technology interest is highest', () => {
    visitEventsPage(buildEventsResponse(technologyBusinessCommunity))
    assertEventOrder(['Technology Summit', 'Business Expo', 'Community Meetup'])
  })

  it('places the business event first when business interest is highest', () => {
    visitEventsPage(buildEventsResponse(businessTechnologyCommunity))
    assertEventOrder(['Business Expo', 'Technology Summit', 'Community Meetup'])
  })

  it('places the community event first when community interest is highest', () => {
    visitEventsPage(buildEventsResponse(communityTechnologyBusiness))
    assertEventOrder(['Community Meetup', 'Technology Summit', 'Business Expo'])
  })

  it('keeps technology ahead of business when the strongest interests are tied and the server sends that order', () => {
    visitEventsPage(buildEventsResponse(technologyBusinessTie))
    assertEventOrder(['Technology Summit', 'Business Expo', 'Community Meetup'])
  })

  it('keeps business ahead of technology when the strongest interests are tied and the server sends that order', () => {
    visitEventsPage(buildEventsResponse(businessTechnologyTie))
    assertEventOrder(['Business Expo', 'Technology Summit', 'Community Meetup'])
  })

  it('keeps business ahead of community when the strongest interests are tied and the server sends that order', () => {
    visitEventsPage(buildEventsResponse(businessCommunityTie))
    assertEventOrder(['Business Expo', 'Community Meetup', 'Technology Summit'])
  })

  it('places a dual-category event by its strongest matched category when technology wins', () => {
    visitEventsPage(buildEventsResponse(dualCategoryTechnologyWins))
    assertEventOrder(['Dual Focus Tech', 'Support Expo', 'Open Community'])
  })

  it('places a dual-category event by its strongest matched category when business wins', () => {
    visitEventsPage(buildEventsResponse(dualCategoryBusinessWins))
    assertEventOrder(['Dual Focus Business', 'Dual Focus Tech', 'Open Community'])
  })

  it('places a dual-category event by its strongest matched category when community wins', () => {
    visitEventsPage(buildEventsResponse(dualCategoryCommunityWins))
    assertEventOrder(['Dual Focus Community', 'Dual Focus Tech', 'Support Expo'])
  })

  it('renders a single matched event in the same order it was returned', () => {
    visitEventsPage(buildEventsResponse(singleEventList))
    assertEventOrder(['Solo Workshop'])
  })

  it('recomputes the order after business interest becomes the highest on reload', () => {
    let requestCount = 0

    cy.intercept('GET', eventsApiPattern, (req) => {
      requestCount += 1
      req.reply({
        statusCode: 200,
        body: buildEventsResponse(requestCount === 1 ? technologyBusinessCommunity : businessTechnologyCommunity),
      })
    }).as('loadEvents')

    cy.visit(eventsPageUrl)
    cy.wait('@loadEvents')
    assertEventOrder(['Technology Summit', 'Business Expo', 'Community Meetup'])

    cy.reload()
    cy.wait('@loadEvents')
    assertEventOrder(['Business Expo', 'Technology Summit', 'Community Meetup'])
  })

  it('recomputes the order after technology interest becomes the highest on reload', () => {
    let requestCount = 0

    cy.intercept('GET', eventsApiPattern, (req) => {
      requestCount += 1
      req.reply({
        statusCode: 200,
        body: buildEventsResponse(requestCount === 1 ? businessTechnologyCommunity : technologyBusinessCommunity),
      })
    }).as('loadEvents')

    cy.visit(eventsPageUrl)
    cy.wait('@loadEvents')
    assertEventOrder(['Business Expo', 'Technology Summit', 'Community Meetup'])

    cy.reload()
    cy.wait('@loadEvents')
    assertEventOrder(['Technology Summit', 'Business Expo', 'Community Meetup'])
  })

  it('recomputes the order after community interest becomes the highest on reload', () => {
    let requestCount = 0

    cy.intercept('GET', eventsApiPattern, (req) => {
      requestCount += 1
      req.reply({
        statusCode: 200,
        body: buildEventsResponse(requestCount === 1 ? technologyBusinessCommunity : communityTechnologyBusiness),
      })
    }).as('loadEvents')

    cy.visit(eventsPageUrl)
    cy.wait('@loadEvents')
    assertEventOrder(['Technology Summit', 'Business Expo', 'Community Meetup'])

    cy.reload()
    cy.wait('@loadEvents')
    assertEventOrder(['Community Meetup', 'Technology Summit', 'Business Expo'])
  })

  it('recomputes the order after interest levels change twice across consecutive reloads', () => {
    let requestCount = 0

    cy.intercept('GET', eventsApiPattern, (req) => {
      requestCount += 1
      const body =
        requestCount === 1
          ? technologyBusinessCommunity
          : requestCount === 2
            ? businessTechnologyCommunity
            : communityTechnologyBusiness

      req.reply({
        statusCode: 200,
        body: buildEventsResponse(body),
      })
    }).as('loadEvents')

    cy.visit(eventsPageUrl)
    cy.wait('@loadEvents')
    assertEventOrder(['Technology Summit', 'Business Expo', 'Community Meetup'])

    cy.reload()
    cy.wait('@loadEvents')
    assertEventOrder(['Business Expo', 'Technology Summit', 'Community Meetup'])

    cy.reload()
    cy.wait('@loadEvents')
    assertEventOrder(['Community Meetup', 'Technology Summit', 'Business Expo'])
  })

  it('keeps equal-interest events in the order returned by the API', () => {
    visitEventsPage(buildEventsResponse(equalInterestEvents))
    assertEventOrder(['Conference Alpha', 'Conference Beta'])
  })
})