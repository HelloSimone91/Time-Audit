import XCTest
@testable import TimeAuditMobile

final class ModelsTests: XCTestCase {
    func testAlignmentLabelsMatchNotionSchema() {
        XCTAssertEqual(AlignmentKind.kindness.notionOption(for: 1), "1 Totally fucking up")
        XCTAssertEqual(AlignmentKind.kindness.notionOption(for: 5), "5 Kind to self and surroundings")
        XCTAssertEqual(AlignmentKind.safety.notionOption(for: 5), "5 Safe to self and surroundings")
        XCTAssertEqual(AlignmentKind.safety.notionOption(for: 3), "3")
    }

    func testNotionDataSourceIsTheLiveTimeAuditSource() {
        XCTAssertEqual(NotionService.dataSourceID, "37906423-ccc1-80b9-96b7-000b196f9131")
    }
}
